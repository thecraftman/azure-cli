# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

from knack.log import get_logger
from knack.util import CLIError

from azure.mgmt.cosmosdb.models import (
    ConsistencyPolicy,
    DatabaseAccountCreateUpdateParameters,
    Location,
    DatabaseAccountKind,
    VirtualNetworkRule
)

logger = get_logger(__name__)

DEFAULT_INDEXING_POLICY = """{
  "indexingMode": "consistent",
  "automatic": true,
  "includedPaths": [
    {
      "path": "/*",
      "indexes": [
        {
          "kind": "Range",
          "dataType": "String",
          "precision": -1
        },
        {
          "kind": "Range",
          "dataType": "Number",
          "precision": -1
        }
      ]
    }
  ]
}"""


def cli_cosmosdb_create(cmd, client,
                        resource_group_name,
                        account_name,
                        locations=None,
                        tags=None,
                        kind=DatabaseAccountKind.global_document_db.value,
                        default_consistency_level=None,
                        max_staleness_prefix=100,
                        max_interval=5,
                        ip_range_filter=None,
                        enable_automatic_failover=None,
                        capabilities=None,
                        enable_virtual_network=None,
                        virtual_network_rules=None,
                        enable_multiple_write_locations=None):
    """Create a new Azure Cosmos DB database account."""
    consistency_policy = None
    if default_consistency_level is not None:
        consistency_policy = ConsistencyPolicy(default_consistency_level=default_consistency_level,
                                               max_staleness_prefix=max_staleness_prefix,
                                               max_interval_in_seconds=max_interval)

    from azure.mgmt.resource import ResourceManagementClient
    from azure.cli.core.commands.client_factory import get_mgmt_service_client
    resource_client = get_mgmt_service_client(cmd.cli_ctx, ResourceManagementClient)
    rg = resource_client.resource_groups.get(resource_group_name)
    resource_group_location = rg.location  # pylint: disable=no-member

    if not locations:
        locations = []
        locations.append(Location(location_name=resource_group_location, failover_priority=0, is_zone_redundant=False))

    params = DatabaseAccountCreateUpdateParameters(
        location=resource_group_location,
        locations=locations,
        tags=tags,
        kind=kind,
        consistency_policy=consistency_policy,
        ip_range_filter=ip_range_filter,
        is_virtual_network_filter_enabled=enable_virtual_network,
        enable_automatic_failover=enable_automatic_failover,
        capabilities=capabilities,
        virtual_network_rules=virtual_network_rules,
        enable_multiple_write_locations=enable_multiple_write_locations)

    async_docdb_create = client.create_or_update(resource_group_name, account_name, params)
    docdb_account = async_docdb_create.result()
    docdb_account = client.get(resource_group_name, account_name)  # Workaround
    return docdb_account


# pylint: disable=too-many-branches
def cli_cosmosdb_update(client,
                        resource_group_name,
                        account_name,
                        locations=None,
                        tags=None,
                        default_consistency_level=None,
                        max_staleness_prefix=None,
                        max_interval=None,
                        ip_range_filter=None,
                        enable_automatic_failover=None,
                        capabilities=None,
                        enable_virtual_network=None,
                        virtual_network_rules=None,
                        enable_multiple_write_locations=None):
    """Update an existing Azure Cosmos DB database account. """
    existing = client.get(resource_group_name, account_name)

    # Workaround until PATCH support for all properties
    # pylint: disable=too-many-boolean-expressions
    if capabilities is not None:
        if locations or \
                default_consistency_level is not None or \
                max_staleness_prefix is not None or \
                max_interval is not None or \
                ip_range_filter is not None or \
                enable_automatic_failover is not None or \
                enable_virtual_network is not None or \
                virtual_network_rules is not None or \
                enable_multiple_write_locations is not None:
            raise CLIError("Cannot set capabilities and update properties at the same time. {0}".format(locations))
        async_docdb_create = client.patch(resource_group_name, account_name, tags=tags, capabilities=capabilities)
        docdb_account = async_docdb_create.result()
        docdb_account = client.get(resource_group_name, account_name)
        return docdb_account

    # Workaround until PATCH support for all properties
    # pylint: disable=too-many-boolean-expressions
    if tags is not None:
        if not locations and \
                default_consistency_level is None and \
                max_staleness_prefix is None and \
                max_interval is None and \
                ip_range_filter is None and \
                enable_automatic_failover is None and \
                enable_virtual_network is None and \
                virtual_network_rules is None and \
                enable_multiple_write_locations is None:
            async_docdb_create = client.patch(resource_group_name, account_name, tags=tags, capabilities=capabilities)
            docdb_account = async_docdb_create.result()
            docdb_account = client.get(resource_group_name, account_name)
            return docdb_account

    update_consistency_policy = False
    if max_interval is not None or \
            max_staleness_prefix is not None or \
            default_consistency_level is not None:
        update_consistency_policy = True

    if max_staleness_prefix is None:
        max_staleness_prefix = existing.consistency_policy.max_staleness_prefix

    if max_interval is None:
        max_interval = existing.consistency_policy.max_interval_in_seconds

    if default_consistency_level is None:
        default_consistency_level = existing.consistency_policy.default_consistency_level

    consistency_policy = None
    if update_consistency_policy:
        consistency_policy = ConsistencyPolicy(default_consistency_level=default_consistency_level,
                                               max_staleness_prefix=max_staleness_prefix,
                                               max_interval_in_seconds=max_interval)
    else:
        consistency_policy = existing.consistency_policy

    if not locations:
        locations = []
        for loc in existing.read_locations:
            locations.append(
                Location(location_name=loc.location_name,
                         failover_priority=loc.failover_priority,
                         is_zone_redundant=loc.is_zone_redundant))

    if ip_range_filter is None:
        ip_range_filter = existing.ip_range_filter

    if enable_automatic_failover is None:
        enable_automatic_failover = existing.enable_automatic_failover

    if enable_virtual_network is None:
        enable_virtual_network = existing.is_virtual_network_filter_enabled

    if virtual_network_rules is None:
        virtual_network_rules = existing.virtual_network_rules

    if tags is None:
        tags = existing.tags

    if enable_multiple_write_locations is None:
        enable_multiple_write_locations = existing.enable_multiple_write_locations
    elif enable_multiple_write_locations != existing.enable_multiple_write_locations \
            and not enable_multiple_write_locations:
        logger.warning("Updating the account from multi master to single master will take 24 hours to complete.")

    params = DatabaseAccountCreateUpdateParameters(
        location=existing.location,
        locations=locations,
        tags=tags,
        kind=existing.kind,
        consistency_policy=consistency_policy,
        ip_range_filter=ip_range_filter,
        enable_automatic_failover=enable_automatic_failover,
        capabilities=existing.capabilities,
        is_virtual_network_filter_enabled=enable_virtual_network,
        virtual_network_rules=virtual_network_rules,
        enable_multiple_write_locations=enable_multiple_write_locations)

    async_docdb_create = client.create_or_update(resource_group_name, account_name, params)
    docdb_account = async_docdb_create.result()
    docdb_account = client.get(resource_group_name, account_name)  # Workaround
    return docdb_account


def cli_cosmosdb_list(client, resource_group_name=None):
    """ Lists all Azure Cosmos DB database accounts within a given resource group or subscription. """
    if resource_group_name:
        return client.list_by_resource_group(resource_group_name)

    return client.list()


def cli_cosmosdb_network_rule_list(client, resource_group_name, account_name):
    """ Lists the virtual network accounts associated with a Cosmos DB account """
    cosmos_db_account = client.get(resource_group_name, account_name)
    return cosmos_db_account.virtual_network_rules


def _get_virtual_network_id(cmd, resource_group_name, subnet, virtual_network):
    from azure.cli.core.commands.client_factory import get_subscription_id
    from msrestazure.tools import is_valid_resource_id, resource_id
    if not is_valid_resource_id(subnet):
        if virtual_network is None:
            raise CLIError("usage error: --subnet ID | --subnet NAME --vnet-name NAME")
        subnet = resource_id(
            subscription=get_subscription_id(cmd.cli_ctx),
            resource_group=resource_group_name,
            namespace='Microsoft.Network', type='virtualNetworks',
            name=virtual_network, child_type_1='subnets', child_name_1=subnet
        )
    return subnet


def cli_cosmosdb_network_rule_add(cmd,
                                  client,
                                  resource_group_name,
                                  account_name,
                                  subnet,
                                  virtual_network=None,
                                  ignore_missing_vnet_service_endpoint=False):
    """ Adds a virtual network rule to an existing Cosmos DB database account """
    subnet = _get_virtual_network_id(cmd, resource_group_name, subnet, virtual_network)
    existing = client.get(resource_group_name, account_name)

    virtual_network_rules = []
    rule_already_exists = False
    for rule in existing.virtual_network_rules:
        virtual_network_rules.append(
            VirtualNetworkRule(id=rule.id,
                               ignore_missing_vnet_service_endpoint=rule.ignore_missing_vnet_service_endpoint))
        if rule.id == subnet:
            rule_already_exists = True
            logger.warning("The rule exists and will be overwritten")

    if not rule_already_exists:
        virtual_network_rules.append(
            VirtualNetworkRule(id=subnet,
                               ignore_missing_vnet_service_endpoint=ignore_missing_vnet_service_endpoint))

    locations = []
    for loc in existing.read_locations:
        locations.append(
            Location(location_name=loc.location_name,
                     failover_priority=loc.failover_priority,
                     is_zone_redundant=loc.is_zone_redundant))

    params = DatabaseAccountCreateUpdateParameters(
        location=existing.location,
        locations=locations,
        tags=existing.tags,
        kind=existing.kind,
        consistency_policy=existing.consistency_policy,
        ip_range_filter=existing.ip_range_filter,
        enable_automatic_failover=existing.enable_automatic_failover,
        capabilities=existing.capabilities,
        is_virtual_network_filter_enabled=True,
        virtual_network_rules=virtual_network_rules,
        enable_multiple_write_locations=existing.enable_multiple_write_locations)

    async_docdb_create = client.create_or_update(resource_group_name, account_name, params)
    docdb_account = async_docdb_create.result()
    docdb_account = client.get(resource_group_name, account_name)  # Workaround
    return docdb_account


def cli_cosmosdb_network_rule_remove(cmd,
                                     client,
                                     resource_group_name,
                                     account_name,
                                     subnet,
                                     virtual_network=None):
    """ Adds a virtual network rule to an existing Cosmos DB database account """
    subnet = _get_virtual_network_id(cmd, resource_group_name, subnet, virtual_network)
    existing = client.get(resource_group_name, account_name)

    virtual_network_rules = []
    rule_removed = False
    for rule in existing.virtual_network_rules:
        if rule.id != subnet:
            virtual_network_rules.append(
                VirtualNetworkRule(id=rule.id,
                                   ignore_missing_vnet_service_endpoint=rule.ignore_missing_vnet_service_endpoint))
        else:
            rule_removed = True
    if not rule_removed:
        raise CLIError("This rule does not exist for the Cosmos DB account")

    locations = []
    for loc in existing.read_locations:
        locations.append(
            Location(location_name=loc.location_name,
                     failover_priority=loc.failover_priority,
                     is_zone_redundant=loc.is_zone_redundant))

    params = DatabaseAccountCreateUpdateParameters(
        location=existing.location,
        locations=locations,
        tags=existing.tags,
        kind=existing.kind,
        consistency_policy=existing.consistency_policy,
        ip_range_filter=existing.ip_range_filter,
        enable_automatic_failover=existing.enable_automatic_failover,
        capabilities=existing.capabilities,
        is_virtual_network_filter_enabled=True,
        virtual_network_rules=virtual_network_rules,
        enable_multiple_write_locations=existing.enable_multiple_write_locations)

    async_docdb_create = client.create_or_update(resource_group_name, account_name, params)
    docdb_account = async_docdb_create.result()
    docdb_account = client.get(resource_group_name, account_name)  # Workaround
    return docdb_account


######################
# data plane APIs
######################

# database operations

def _get_database_link(database_id):
    return 'dbs/{}'.format(database_id)


def _get_collection_link(database_id, collection_id):
    return 'dbs/{}/colls/{}'.format(database_id, collection_id)


def _get_offer_link(database_id, offer_id):
    return 'dbs/{}/colls/{}'.format(database_id, offer_id)


def cli_cosmosdb_database_exists(client, database_id):
    """Returns a boolean indicating whether the database exists """
    return len(list(client.QueryDatabases(
        {'query': 'SELECT * FROM root r WHERE r.id=@id',
         'parameters': [{'name': '@id', 'value': database_id}]}))) > 0


def cli_cosmosdb_database_show(client, database_id):
    """Shows an Azure Cosmos DB database """
    return client.ReadDatabase(_get_database_link(database_id))


def cli_cosmosdb_database_list(client):
    """Lists all Azure Cosmos DB databases """
    return list(client.ReadDatabases())


def cli_cosmosdb_database_create(client, database_id, throughput=None):
    """Creates an Azure Cosmos DB database """
    return client.CreateDatabase({'id': database_id}, {'offerThroughput': throughput})


def cli_cosmosdb_database_delete(client, database_id):
    """Deletes an Azure Cosmos DB database """
    client.DeleteDatabase(_get_database_link(database_id))


# collection operations

def cli_cosmosdb_collection_exists(client, database_id, collection_id):
    """Returns a boolean indicating whether the collection exists """
    return len(list(client.QueryContainers(
        _get_database_link(database_id),
        {'query': 'SELECT * FROM root r WHERE r.id=@id',
         'parameters': [{'name': '@id', 'value': collection_id}]}))) > 0


def cli_cosmosdb_collection_show(client, database_id, collection_id):
    """Shows an Azure Cosmos DB collection and its offer """
    collection = client.ReadContainer(_get_collection_link(database_id, collection_id))
    offer = _find_offer(client, collection['_self'])
    return {'collection': collection, 'offer': offer}


def cli_cosmosdb_collection_list(client, database_id):
    """Lists all Azure Cosmos DB collections """
    return list(client.ReadContainers(_get_database_link(database_id)))


def cli_cosmosdb_collection_delete(client, database_id, collection_id):
    """Deletes an Azure Cosmos DB collection """
    client.DeleteContainer(_get_collection_link(database_id, collection_id))


def _populate_collection_definition(collection,
                                    partition_key_path=None,
                                    default_ttl=None,
                                    indexing_policy=None):
    if all(arg is None for arg in [partition_key_path, default_ttl, indexing_policy]):
        return False

    if partition_key_path is not None:
        if 'partitionKey' not in collection:
            collection['partitionKey'] = {}
        collection['partitionKey'] = {'paths': [partition_key_path], 'kind': 'Hash'}

    if default_ttl is not None:
        if default_ttl == 0 and "defaultTtl" in collection:
            del collection['defaultTtl']
        elif default_ttl != 0:
            collection['defaultTtl'] = default_ttl

    if indexing_policy is not None:
        collection['indexingPolicy'] = indexing_policy

    return True


def cli_cosmosdb_collection_create(client,
                                   database_id,
                                   collection_id,
                                   throughput=None,
                                   partition_key_path=None,
                                   default_ttl=None,
                                   indexing_policy=DEFAULT_INDEXING_POLICY):
    """Creates an Azure Cosmos DB collection """
    collection = {'id': collection_id}

    options = {}
    if throughput:
        options['offerThroughput'] = throughput

    _populate_collection_definition(collection,
                                    partition_key_path,
                                    default_ttl,
                                    indexing_policy)

    created_collection = client.CreateContainer(_get_database_link(database_id), collection,
                                                options)
    offer = _find_offer(client, created_collection['_self'])
    return {'collection': created_collection, 'offer': offer}


def _find_offer(client, collection_self_link):
    logger.debug('finding offer')
    offers = client.ReadOffers()
    for o in offers:
        if o['resource'] == collection_self_link:
            return o
    return None


def cli_cosmosdb_collection_update(client,
                                   database_id,
                                   collection_id,
                                   throughput=None,
                                   default_ttl=None,
                                   indexing_policy=None):
    """Updates an Azure Cosmos DB collection """
    logger.debug('reading collection')
    collection = client.ReadContainer(_get_collection_link(database_id, collection_id))
    result = {}

    if (_populate_collection_definition(collection,
                                        None,
                                        default_ttl,
                                        indexing_policy)):
        logger.debug('replacing collection')
        result['collection'] = client.ReplaceContainer(
            _get_collection_link(database_id, collection_id), collection)

    if throughput:
        logger.debug('updating offer')
        offer = _find_offer(client, collection['_self'])

        if offer is None:
            raise CLIError("Cannot find offer for collection {}".format(collection_id))

        if 'content' not in offer:
            offer['content'] = {}
        offer['content']['offerThroughput'] = throughput

        result['offer'] = client.ReplaceOffer(offer['_self'], offer)
    return result
