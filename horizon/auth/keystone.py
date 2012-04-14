import logging

from django.contrib.auth import logout as auth_logout
from django.contrib.auth.signals import user_logged_in
from django.utils.translation import ugettext as _

from horizon import api
from horizon import exceptions
from keystoneclient import exceptions as keystone_exceptions

LOG = logging.getLogger(__name__)

USER_SESSION_KEY = '_auth_keystone_user'

def _cache_user(sender, request, user, **kwargs):
    request._cached_user = user
    request.session._keystone_user = user

# Maybe needs some more restrictions
user_logged_in.connect(_cache_user)

class KeystoneBackend(object):
    def get_user(user_id):
        # Deliberately allows django.contrib.auth.AnonymousUser() to be set.
        # Middleware and signal sets this correctly when appropriate.
        pass

    def _create_user(request, token):
        return User(id=token.user['user_id'],
                    token=token.id,
                    user=token.user['name'],
                    tenant_id=token.tenant['id'],
                    tenant_name=token.tenant['name'],
                    service_catalog=token.serviceCatalog,
                    roles=token.user['roles'],
                    request=request)

    def authenticate(self, request, data):
        if data.get('tenant', None):
            try:
                token = api.token_create(request,
                                         data.get('tenant'),
                                         data['username'],
                                         data['password'])
                tenants = api.tenant_list_for_token(request, token.id)
            except:
                msg = _('Unable to authenticate for that project.')
                exceptions.handle(request,
                                  message=msg,
                                  escalate=True)

            return self._create_user(request, token)

        elif data.get('username', None):
            try:
                unscoped_token = api.token_create(request,
                                                  '',
                                                  data['username'],
                                                  data['password'])
            except keystone_exceptions.Unauthorized:
                exceptions.handle(request,
                                  _('Invalid user name or password.'))
            except:
                # If we get here we don't want to show a stack trace to the
                # user. However, if we fail here, there may be bad session
                # data that's been cached already.

                # Log out all the way, just to be sure
                auth_logout(request)
                exceptions.handle(request,
                                  message=_("An error occurred authenticating."
                                            " Please try again later."),
                                  escalate=True)

            # Unscoped token
            request.session['unscoped_token'] = unscoped_token.id

            # Get the tenant list, and log in using first tenant
            # FIXME (anthony): add tenant chooser here?
            try:
                tenants = api.tenant_list_for_token(request, unscoped_token.id)
            except:
                exceptions.handle(request)
                tenants = []

            # Abort if there are no valid tenants for this user
            if not tenants:
                messages.error(request,
                               _('You are not authorized for any projects.') %
                                {"user": data['username']},
                               extra_tags="login")
                # Fixme (PaulM): this might be a bug
                return

            # Create a token.
            # NOTE(gabriel): Keystone can return tenants that you're
            # authorized to administer but not to log into as a user, so in
            # the case of an Unauthorized error we should iterate through
            # the tenants until one succeeds or we've failed them all.
            while tenants:
                tenant = tenants.pop()
                try:
                    token = api.token_create_scoped(request,
                                                    tenant.id,
                                                    unscoped_token.id)
                    break
                except:
                    # This will continue for recognized Unauthorized
                    # exceptions from keystoneclient.
                    exceptions.handle(request, ignore=True)
                    token = None
            if token is None:
                raise exceptions.NotAuthorized(
                    _("You are not authorized for any available projects."))

            return self._create_user(request, token)


class User(object):
    """ The main user class which Horizon expects.

    .. attribute:: token

        The id of the Keystone token associated with the current user/tenant.

    .. attribute:: username

        The name of the current user.

    .. attribute:: tenant_id

        The id of the Keystone tenant for the current user/token.

    .. attribute:: tenant_name

        The name of the Keystone tenant for the current user/token.

    .. attribute:: service_catalog

        The ``ServiceCatalog`` data returned by Keystone.

    .. attribute:: roles

        A list of dictionaries containing role names and ids as returned
        by Keystone.

    .. attribute:: admin

        Boolean value indicating whether or not this user has admin
        privileges. Internally mapped to :meth:`horizon.users.User.is_admin`.
    """
    def __init__(self, id=None, token=None, user=None, tenant_id=None,
                    service_catalog=None, tenant_name=None, roles=None,
                    authorized_tenants=None, request=None):
        self.id = id
        self.token = token
        self.username = user
        self.tenant_id = tenant_id
        self.tenant_name = tenant_name
        self.service_catalog = service_catalog
        self.roles = roles or []
        self._authorized_tenants = authorized_tenants
        # Store the request for lazy fetching of auth'd tenants
        self._request = request

    def is_authenticated(self):
        """
        Evaluates whether this :class:`.User` instance has been authenticated.
        Returns ``True`` or ``False``.
        """
        # TODO: deal with token expiration
        return self.token

    @property
    def admin(self):
        return self.is_admin()

    def is_admin(self):
        """
        Evaluates whether this user has admin privileges. Returns
        ``True`` or ``False``.
        """
        for role in self.roles:
            if role['name'].lower() == 'admin':
                return True
        return False

    def get_and_delete_messages(self):
        """
        Placeholder function for parity with
        ``django.contrib.auth.models.User``.
        """
        return []

    @property
    def authorized_tenants(self):
        if self.is_authenticated() and self._authorized_tenants is None:
            try:
                token = self._request.session.get("unscoped_token", self.token)
                authd = api.tenant_list_for_token(self._request, token)
            except:
                authd = []
                LOG.exception('Could not retrieve tenant list.')
            self._authorized_tenants = authd
        return self._authorized_tenants

    @authorized_tenants.setter
    def authorized_tenants(self, tenant_list):
        self._authorized_tenants = tenant_list
