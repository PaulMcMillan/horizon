import logging

from django import shortcuts
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _

from horizon import api
from horizon import tables


LOG = logging.getLogger(__name__)


class RenameNetworkLink(tables.LinkAction):
    name = "rename_network"
    verbose_name = _("Rename Network")
    url = "horizon:nova:networks:rename"
    attrs = {"class": "ajax-modal"}

class CreateNetworkLink(tables.LinkAction):
    name = "create_network"
    verbose_name = _("Create New Network")
    url = "horizon:nova:networks:create"
    attrs = {"class": "ajax-modal btn small"}

class DeleteNetworkAction(tables.DeleteAction):
    data_type_singular = _("Network")
    data_type_plural = _("Networks")

    def delete(self, request, obj_id):
        api.quantum_delete_network(request, obj_id)

class NetworksTable(tables.DataTable):
    id = tables.Column('id', verbose_name=_('Id'))
    name = tables.Column('name', verbose_name=_('Name'))
    used = tables.Column('used', verbose_name=_('Used'))
    available = tables.Column('available', verbose_name=_('Available'))
    total = tables.Column('total', verbose_name=_('Total'))
    #tenant = tables.Column('tenant', verbose_name=_('Tenant'))

    def get_object_id(self, datum):
        return datum['id']

    def get_object_display(self, obj):
        return obj['name']

    class Meta:
        name = "networks"
        verbose_name = _("Networks")
        row_actions = (DeleteNetworkAction, RenameNetworkLink,)
        table_actions = (CreateNetworkLink, DeleteNetworkAction,)


class DeletePortAction(tables.DeleteAction):
    data_type_singular = _("Port")
    data_type_plural = _("Ports")

    def delete(self, request, obj_id):
        import pdb;pdb.set_trace()
        api.quantum_delete_port(request, data['network'], data['port'])

class NetworkDetailsTable(tables.DataTable):
    id = tables.Column('id', verbose_name=_('Id'))
    state = tables.Column('state', verbose_name=_('State'))
    attachment = tables.Column('attachment', verbose_name=_('Attachment'))
    
    def get_object_id(self, datum):
        import pdb;pdb.set_trace()
        return datum['id']

    def get_object_display(self, obj):
        return obj['id']

    class Meta:
        name = "network_details"
        verbose_name = _("Network Port Details")
        row_actions = (DeletePortAction,)
        table_actions = (DeletePortAction,)
