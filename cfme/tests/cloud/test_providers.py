# -*- coding: utf-8 -*-
# pylint: disable=E1101
# pylint: disable=W0621
import fauxfactory
import uuid

import pytest

from manageiq_client.api import APIException

import utils.error as error
import cfme.fixtures.pytest_selenium as sel
from cfme import Credential
from cfme.exceptions import FlashMessageException
from cfme.cloud.provider import (discover, wait_for_a_provider,
    CloudProvider, prop_region)
from cfme import test_requirements
from cfme.cloud.provider.ec2 import EC2Provider
from cfme.cloud.provider.openstack import OpenStackProvider
from cfme.web_ui import fill, flash
from utils import testgen, version, providers
from utils.appliance.implementations.ui import navigate_to
from utils.update import update
from utils.log import logger

pytest_generate_tests = testgen.generate([CloudProvider], scope="function")


@pytest.fixture(scope="module")
def setup_a_provider():
    return providers.setup_a_provider_by_class(CloudProvider)


@pytest.mark.tier(3)
@test_requirements.discovery
def test_empty_discovery_form_validation():
    """ Tests that the flash message is correct when discovery form is empty."""
    discover(None, d_type="Amazon")
    ident = version.pick({version.LOWEST: 'User ID',
                          '5.4': 'Username'})
    flash.assert_message_match('{} is required'.format(ident))


@pytest.mark.tier(3)
@test_requirements.discovery
def test_discovery_cancelled_validation():
    """ Tests that the flash message is correct when discovery is cancelled."""
    discover(None, cancel=True, d_type="Amazon")
    msg = version.pick(
        {version.LOWEST: 'Amazon Cloud Providers Discovery was cancelled by the user',
         '5.5': 'Cloud Providers Discovery was cancelled by the user'})
    flash.assert_message_match(msg)


@pytest.mark.tier(3)
@test_requirements.discovery
def test_add_cancelled_validation(request):
    """Tests that the flash message is correct when add is cancelled."""
    prov = EC2Provider()
    request.addfinalizer(prov.delete_if_exists)
    prov.create(cancel=True)
    flash.assert_message_match({
        version.LOWEST: 'Add of new Cloud Provider was cancelled by the user',
        '5.5': 'Add of Cloud Provider was cancelled by the user'})


@pytest.mark.tier(3)
def test_password_mismatch_validation():
    cred = Credential(
        principal=fauxfactory.gen_alphanumeric(5),
        secret=fauxfactory.gen_alphanumeric(5),
        verify_secret=fauxfactory.gen_alphanumeric(7))

    discover(cred, d_type="Amazon")
    flash.assert_message_match('Password/Verify Password do not match')


@pytest.mark.tier(3)
@pytest.mark.uncollect()
@pytest.mark.usefixtures('has_no_cloud_providers')
@test_requirements.discovery
def test_providers_discovery_amazon():
    # This test was being uncollected anyway, and needs to be parametrized and not directory call
    # out to specific credential keys
    # amazon_creds = get_credentials_from_config('cloudqe_amazon')
    # discover(amazon_creds, d_type="Amazon")
    flash.assert_message_match('Amazon Cloud Providers: Discovery successfully initiated')
    wait_for_a_provider()


@pytest.mark.tier(3)
@pytest.mark.usefixtures('has_no_cloud_providers')
@test_requirements.discovery
def test_provider_add_with_bad_credentials(provider):
    """ Tests provider add with bad credentials

    Metadata:
        test_flag: crud
    """
    if provider.type == "azure":
        flash = (
            "Credential validation was not successful: Incorrect credentials - "
            "check your Azure Client ID and Client Key"
        )
        principal = str(uuid.uuid4())
    else:
        flash = 'Login failed due to a bad username or password.'
        principal = "bad"
    provider.credentials['default'] = provider.Credential(
        principal=principal,
        secret='reallybad',
    )
    with error.expected(flash):
        provider.create(validate_credentials=True)


@pytest.mark.tier(2)
@pytest.mark.usefixtures('has_no_cloud_providers')
@test_requirements.discovery
def test_provider_crud(provider):
    """ Tests provider add with good credentials

    Metadata:
        test_flag: crud
    """
    provider.create()
    provider.validate_stats(ui=True)

    old_name = provider.name
    with update(provider):
        provider.name = str(uuid.uuid4())  # random uuid

    with update(provider):
        provider.name = old_name  # old name

    provider.delete(cancel=False)
    provider.wait_for_delete()


@pytest.mark.tier(3)
@test_requirements.discovery
def test_type_required_validation(request, soft_assert):
    """Test to validate type while adding a provider"""
    prov = CloudProvider()

    request.addfinalizer(prov.delete_if_exists)
    if version.current_version() < "5.5":
        with error.expected('Type is required'):
            prov.create()
    else:
        navigate_to(prov, 'Add')
        fill(prov.properties_form.name_text, "foo")
        soft_assert("ng-invalid-required" in prov.properties_form.type_select.classes)
        soft_assert(not prov.add_provider_button.can_be_clicked)


@pytest.mark.tier(3)
@test_requirements.discovery
def test_name_required_validation(request):
    """Tests to validate the name while adding a provider"""
    prov = EC2Provider(
        name=None,
        region='us-east-1')

    request.addfinalizer(prov.delete_if_exists)
    if version.current_version() < "5.5":
        with error.expected("Name can't be blank"):
            prov.create()
    else:
        # It must raise an exception because it keeps on the form
        with error.expected(FlashMessageException):
            prov.create()
        assert prov.properties_form.name_text.angular_help_block == "Required"


@pytest.mark.tier(3)
def test_region_required_validation(request, soft_assert):
    """Tests to validate the region while adding a provider"""
    prov = EC2Provider(
        name=fauxfactory.gen_alphanumeric(5),
        region=None)

    request.addfinalizer(prov.delete_if_exists)
    if version.current_version() < "5.5":
        with error.expected('Region is not included in the list'):
            prov.create()
    else:
        with error.expected(FlashMessageException):
            prov.create()
        soft_assert(
            "ng-invalid-required" in prov.properties_form.region_select.classes)


@pytest.mark.tier(3)
@test_requirements.discovery
def test_host_name_required_validation(request):
    """Test to validate the hostname while adding a provider"""
    prov = OpenStackProvider(
        name=fauxfactory.gen_alphanumeric(5),
        hostname=None,
        ip_address=fauxfactory.gen_ipaddr(prefix=[10]))

    request.addfinalizer(prov.delete_if_exists)
    if version.current_version() < "5.5":
        with error.expected("Host Name can't be blank"):
            prov.create()
    else:
        # It must raise an exception because it keeps on the form
        with error.expected(FlashMessageException):
            prov.create()
        assert prov.properties_form.hostname_text.angular_help_block == "Required"


@pytest.mark.tier(3)
@pytest.mark.uncollectif(lambda: version.current_version() > '5.4')
def test_ip_address_required_validation(request):
    """Test to validate the ip address while adding a provider"""
    prov = OpenStackProvider(
        name=fauxfactory.gen_alphanumeric(5),
        hostname=fauxfactory.gen_alphanumeric(5),
        ip_address=None)

    request.addfinalizer(prov.delete_if_exists)
    with error.expected("IP Address can't be blank"):
        prov.create()


@pytest.mark.tier(3)
def test_api_port_blank_validation(request):
    """Test to validate blank api port while adding a provider"""
    prov = OpenStackProvider(
        name=fauxfactory.gen_alphanumeric(5),
        hostname=fauxfactory.gen_alphanumeric(5),
        ip_address=fauxfactory.gen_ipaddr(prefix=[10]),
        api_port='')

    request.addfinalizer(prov.delete_if_exists)
    if version.current_version() < "5.5":
        prov.create()
    else:
        # It must raise an exception because it keeps on the form
        with error.expected(FlashMessageException):
            prov.create()
        assert prov.properties_form.api_port.angular_help_block == "Required"


@pytest.mark.tier(3)
def test_user_id_max_character_validation():
    cred = Credential(principal=fauxfactory.gen_alphanumeric(51))
    discover(cred, d_type="Amazon")


@pytest.mark.tier(3)
def test_password_max_character_validation():
    password = fauxfactory.gen_alphanumeric(51)
    cred = Credential(
        principal=fauxfactory.gen_alphanumeric(5),
        secret=password,
        verify_secret=password)
    discover(cred, d_type="Amazon")


@pytest.mark.tier(3)
@test_requirements.discovery
def test_name_max_character_validation(request, setup_a_provider):
    """Test to validate max character for name field"""
    provider = setup_a_provider
    request.addfinalizer(lambda: provider.delete_if_exists(cancel=False))
    name = fauxfactory.gen_alphanumeric(255)
    provider.update({'name': name})
    provider.name = name
    assert provider.exists


@pytest.mark.tier(3)
def test_hostname_max_character_validation(request):
    """Test to validate max character for hostname field"""
    prov = OpenStackProvider(
        name=fauxfactory.gen_alphanumeric(5),
        hostname=fauxfactory.gen_alphanumeric(256),
        ip_address='10.10.10.13')
    try:
        prov.create()
    except FlashMessageException:
        element = sel.move_to_element(prov.properties_form.locators["hostname_text"])
        text = element.get_attribute('value')
        assert text == prov.hostname[0:255]


@pytest.mark.tier(3)
@test_requirements.discovery
def test_api_port_max_character_validation(request):
    """Test to validate max character for api port field"""
    prov = OpenStackProvider(
        name=fauxfactory.gen_alphanumeric(5),
        hostname=fauxfactory.gen_alphanumeric(5),
        ip_address='10.10.10.15',
        api_port=fauxfactory.gen_alphanumeric(16))
    try:
        prov.create()
    except FlashMessageException:
        element = sel.move_to_element(prov.properties_form.locators["api_port"])
        text = element.get_attribute('value')
        assert text == prov.api_port[0:15]


@pytest.mark.tier(3)
@pytest.mark.uncollectif(lambda: version.current_version() < "5.5")
@pytest.mark.meta(blockers=[1278036])
def test_openstack_provider_has_api_version():
    """Check whether the Keystone API version field is present for Openstack."""
    prov = CloudProvider()
    navigate_to(prov, 'Add')
    fill(prop_region.properties_form, {"type_select": "OpenStack"})
    pytest.sel.wait_for_ajax()
    assert pytest.sel.is_displayed(
        prov.properties_form.api_version), "API version select is not visible"


class TestProvidersRESTAPI(object):
    @pytest.yield_fixture(scope="function")
    def arbitration_profiles(self, rest_api, setup_a_provider):
        num_profiles = 2
        provider = rest_api.collections.providers.get(name=setup_a_provider.name)
        body = []
        providers = [{'id': provider.id}, {'href': provider.href}]
        for i in range(num_profiles):
            body.append({
                'name': 'test_settings_{}'.format(fauxfactory.gen_alphanumeric(5)),
                'provider': providers[i % 2]
            })
        response = rest_api.collections.arbitration_profiles.action.create(*body)
        assert len(response) == num_profiles

        yield response

        try:
            rest_api.collections.arbitration_profiles.action.delete(*response)
        except APIException:
            # profiles can be deleted by tests, just log warning
            logger.warning("Failed to delete arbitration profiles.")

    @pytest.mark.tier(3)
    @pytest.mark.uncollectif(lambda: version.current_version() < '5.7')
    @pytest.mark.parametrize('from_detail', [True, False], ids=['from_detail', 'from_collection'])
    def test_cloud_networks_query(self, setup_a_provider, rest_api, from_detail):
        """Tests querying cloud providers and cloud_networks collection for network info.

        Metadata:
            test_flag: rest
        """
        if from_detail:
            networks = rest_api.collections.providers.get(name=setup_a_provider.name).cloud_networks
        else:
            networks = rest_api.collections.cloud_networks
        assert rest_api.response.status_code == 200
        assert len(networks) > 0
        assert len(networks) == networks.subcount
        assert len(networks.find_by(enabled=True)) >= 1
        assert 'CloudNetwork' in networks[0].type

    @pytest.mark.tier(3)
    @pytest.mark.uncollectif(lambda: version.current_version() < '5.7')
    def test_security_groups_query(self, setup_a_provider, rest_api):
        """Tests querying cloud networks subcollection for security groups info.

        Metadata:
            test_flag: rest
        """
        network = rest_api.collections.providers.get(name=setup_a_provider.name).cloud_networks[0]
        network.reload(attributes='security_groups')
        security_groups = network.security_groups
        # "security_groups" needs to be present, even if it's just an empty list
        assert isinstance(security_groups, list)
        # if it's not empty, check type
        if len(security_groups) > 0:
            assert 'SecurityGroup' in security_groups[0]['type']

    @pytest.mark.tier(3)
    @pytest.mark.uncollectif(lambda: version.current_version() < '5.7')
    def test_create_arbitration_profiles(self, rest_api, arbitration_profiles):
        """Tests creation of arbitration profiles.

        Metadata:
            test_flag: rest
        """
        for profile in arbitration_profiles:
            record = rest_api.collections.arbitration_profiles.get(id=profile.id)
            assert rest_api.response.status_code == 200
            assert record._data == profile._data
            assert 'ArbitrationProfile' in profile.type

    @pytest.mark.tier(3)
    @pytest.mark.uncollectif(lambda: version.current_version() < '5.7')
    @pytest.mark.parametrize('method', ['post', 'delete'])
    def test_delete_arbitration_profiles_from_detail(self, rest_api, arbitration_profiles, method):
        """Tests delete arbitration profiles from detail.

        Metadata:
            test_flag: rest
        """
        status = 204 if method == 'delete' else 200
        for entity in arbitration_profiles:
            entity.action.delete(force_method=method)
            assert rest_api.response.status_code == status
            with error.expected('ActiveRecord::RecordNotFound'):
                entity.action.delete(force_method=method)
            assert rest_api.response.status_code == 404

    @pytest.mark.tier(3)
    @pytest.mark.uncollectif(lambda: version.current_version() < '5.7')
    def test_delete_arbitration_profiles_from_collection(self, rest_api, arbitration_profiles):
        """Tests delete arbitration profiles from collection.

        Metadata:
            test_flag: rest
        """
        collection = rest_api.collections.arbitration_profiles
        collection.action.delete(*arbitration_profiles)
        assert rest_api.response.status_code == 200
        with error.expected('ActiveRecord::RecordNotFound'):
            collection.action.delete(*arbitration_profiles)
        assert rest_api.response.status_code == 404

    @pytest.mark.tier(3)
    @pytest.mark.uncollectif(lambda: version.current_version() < '5.7')
    @pytest.mark.parametrize('from_detail', [True, False], ids=['from_detail', 'from_collection'])
    def test_edit_arbitration_profiles(self, rest_api, arbitration_profiles, from_detail):
        """Tests editing of arbitration profiles.

        Metadata:
            test_flag: rest
        """
        response_len = len(arbitration_profiles)
        zone = rest_api.collections.availability_zones[-1]
        locators = [{'id': zone.id}, {'href': zone.href}]
        new = [{'availability_zone': locators[i % 2]} for i in range(response_len)]
        if from_detail:
            edited = []
            for i in range(response_len):
                edited.append(arbitration_profiles[i].action.edit(**new[i]))
                assert rest_api.response.status_code == 200
        else:
            for i in range(response_len):
                new[i].update(arbitration_profiles[i]._ref_repr())
            edited = rest_api.collections.arbitration_profiles.action.edit(*new)
            assert rest_api.response.status_code == 200
        assert len(edited) == response_len
        for i in range(response_len):
            assert edited[i].availability_zone_id == zone.id
