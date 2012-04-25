# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
# Copyright 2012 Nebula, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Forms used for Horizon's auth mechanisms.
"""

import logging

from django import shortcuts
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME, authenticate, login as auth_login
from django.utils.translation import ugettext as _
from keystoneclient import exceptions as keystone_exceptions

from horizon import api
from horizon import base
from horizon import exceptions
from horizon import forms


LOG = logging.getLogger(__name__)


class Login(forms.SelfHandlingForm):
    """ Form used for logging in a user.

    Handles authentication with Keystone, choosing a tenant, and fetching
    a scoped token token for that tenant. Redirects to the URL returned
    by :meth:`horizon.get_user_home` if successful.

    Subclass of :class:`~horizon.forms.SelfHandlingForm`.
    """
    region = forms.ChoiceField(label=_("Region"), required=False)
    username = forms.CharField(label=_("User Name"))
    password = forms.CharField(label=_("Password"),
                               widget=forms.PasswordInput(render_value=False))

    def __init__(self, *args, **kwargs):
        super(Login, self).__init__(*args, **kwargs)
        # FIXME(gabriel): When we switch to region-only settings, we can
        # remove this default region business.
        default_region = (settings.OPENSTACK_KEYSTONE_URL, "Default Region")
        regions = getattr(settings, 'AVAILABLE_REGIONS', [default_region])
        self.fields['region'].choices = regions
        if len(regions) == 1:
            self.fields['region'].initial = default_region[0]
            self.fields['region'].widget = forms.widgets.HiddenInput()

    def handle(self, request, data):
        # For now we'll allow fallback to OPENSTACK_KEYSTONE_URL if the
        # form post doesn't include a region.
        endpoint = data.get('region', None) or settings.OPENSTACK_KEYSTONE_URL
        region_name = dict(self.fields['region'].choices)[endpoint]
        request.session['region_endpoint'] = endpoint
        request.session['region_name'] = region_name

        redirect_to = request.REQUEST.get(REDIRECT_FIELD_NAME, "")

        user = authenticate(request=request, data=data)
        auth_login(request, user)
        redirect = redirect_to or base.Horizon.get_user_home(user)
        return shortcuts.redirect(redirect)


class LoginWithTenant(Login):
    """
    Exactly like :class:`.Login` but includes the tenant id as a field
    so that the process of choosing a default tenant is bypassed.
    """
    region = forms.ChoiceField(required=False)
    username = forms.CharField(max_length="20",
                       widget=forms.TextInput(attrs={'readonly': 'readonly'}))
    tenant = forms.CharField(widget=forms.HiddenInput())
