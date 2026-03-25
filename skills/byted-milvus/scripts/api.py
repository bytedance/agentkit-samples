from abc import ABC, abstractmethod
from typing import Any

class ApiError(Exception):
    pass

class MilvusApi(ABC):
    @abstractmethod
    def _call(self, method: str, action: str, body: Any) -> Any: pass

    # Standard Milvus APIs
    def describe_instances(self, body: Any) -> Any: return self._call("POST", "DescribeInstances", body)
    def describe_instance_detail(self, body: Any) -> Any: return self._call("POST", "DescribeInstanceDetail", body)
    def create_instance_one_step(self, body: Any) -> Any: return self._call("POST", "CreateInstanceOneStep", body)
    def scale_instance(self, body: Any) -> Any: return self._call("POST", "ScaleInstance", body)
    def release_instance(self, body: Any) -> Any: return self._call("POST", "ReleaseInstance", body)
    def describe_available_version(self, body: Any) -> Any: return self._call("POST", "DescribeAvailableVersion", body)
    def describe_available_spec_v2(self, body: Any) -> Any: return self._call("POST", "DescribeAvailableSpecV2", body)
    
    # Serverless (MS) Milvus APIs
    def m_s_describe_instances(self, body: Any) -> Any: return self._call("POST", "MSDescribeInstances", body)
    def m_s_describe_instance(self, body: Any) -> Any: return self._call("POST", "MSDescribeInstance", body)
    def m_s_create_instance_one_step(self, body: Any) -> Any: return self._call("POST", "MSCreateInstanceOneStep", body)
    def m_s_release_instance(self, body: Any) -> Any: return self._call("POST", "MSReleaseInstance", body)
    def m_s_modify_public_domain(self, body: Any) -> Any: return self._call("POST", "MSModifyPublicDomain", body)
    def m_s_modify_endpoint_allow_group(self, body: Any) -> Any: return self._call("POST", "MSModifyEndpointAllowGroup", body)

    # Regular Milvus ModifyPublicDomain (Universal)
    def modify_public_domain(self, body: Any) -> Any: return self._call("POST", "ModifyPublicDomain", body)
    def modify_endpoint_allow_group(self, body: Any) -> Any: return self._call("POST", "ModifyEndpointAllowGroup", body)

class VpcApi(ABC):
    @abstractmethod
    def _call(self, method: str, action: str, body: Any) -> Any: pass

    def describe_vpcs(self, body: Any) -> Any: return self._call("GET", "DescribeVpcs", body)
    def describe_subnets(self, body: Any) -> Any: return self._call("GET", "DescribeSubnets", body)
    def describe_eip_addresses(self, body: Any) -> Any: return self._call("GET", "DescribeEipAddresses", body)
    def describe_eip_address_attributes(self, body: Any) -> Any: return self._call("GET", "DescribeEipAddressAttributes", body)
    def allocate_eip_address(self, body: Any) -> Any: return self._call("GET", "AllocateEipAddress", body)
    def release_eip_address(self, body: Any) -> Any: return self._call("GET", "ReleaseEipAddress", body)
