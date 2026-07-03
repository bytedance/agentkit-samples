#!/usr/bin/env python3
# Copyright (c) 2026 Beijing Volcano Engine Technology Ltd.
# SPDX-License-Identifier: Apache-2.0

from __future__ import print_function

import argparse
from typing import Any, List, NamedTuple

from common import parse_json_payload, print_error, print_result, universal_call


class ActionSpec(NamedTuple):
    command: str
    action: str
    method: str
    pages: str


CONSOLE_ACTIONS = [
    ActionSpec("add_scene_data", "AddSceneData", "POST", "SceneDevelopment"),
    ActionSpec(
        "adjust_gray_release_traffic",
        "AdjustGrayReleaseTraffic",
        "POST",
        "SceneDevelopment",
    ),
    ActionSpec(
        "answer_agentic_chat_question",
        "AnswerAgenticChatQuestion",
        "POST",
        "SceneDevelopment",
    ),
    ActionSpec(
        "apply_search_config_version", "ApplySearchConfigVersion", "POST", "DataSource"
    ),
    ActionSpec(
        "cancel_agentic_chat_turn", "CancelAgenticChatTurn", "POST", "SceneDevelopment"
    ),
    ActionSpec(
        "check_advanced_search_config_version",
        "CheckAdvancedSearchConfigVersion",
        "POST",
        "DataSource",
    ),
    ActionSpec(
        "check_builtin_deployment",
        "CheckBuiltinDeployment",
        "POST",
        "Home,InferenceService,SceneDevelopment",
    ),
    ActionSpec(
        "check_indexer_data_source_name_exist",
        "CheckIndexerDataSourceNameExist",
        "GET",
        "DataSource",
    ),
    ActionSpec(
        "check_indexer_name_exist", "CheckIndexerNameExist", "GET", "DataSource"
    ),
    ActionSpec("check_job_under_indexer", "CheckJobUnderIndexer", "GET", "DataSource"),
    ActionSpec("check_scene_demo", "CheckSceneDemo", "GET", "Home"),
    ActionSpec(
        "complete_gray_release", "CompleteGrayRelease", "POST", "SceneDevelopment"
    ),
    ActionSpec(
        "create_ai_deployment", "CreateAIDeployment", "POST", "InferenceService"
    ),
    ActionSpec("create_ai_model", "CreateAIModel", "POST", "ModelsManagement"),
    ActionSpec(
        "create_ai_network",
        "CreateAINetwork",
        "POST",
        "InferenceService,SceneDevelopment",
    ),
    ActionSpec("create_agentic_chat", "CreateAgenticChat", "POST", "SceneDevelopment"),
    ActionSpec(
        "create_agentic_data_source",
        "CreateAgenticDataSource",
        "POST",
        "AgenticDataSource",
    ),
    ActionSpec(
        "create_agentic_data_source_scene_binding",
        "CreateAgenticDataSourceSceneBinding",
        "POST",
        "SceneDevelopment",
    ),
    ActionSpec(
        "create_agentic_mcp_tool", "CreateAgenticMcpTool", "POST", "SceneDevelopment"
    ),
    ActionSpec(
        "create_agentic_scene", "CreateAgenticScene", "POST", "SceneDevelopment"
    ),
    ActionSpec(
        "create_agentic_variable", "CreateAgenticVariable", "POST", "SceneDevelopment"
    ),
    ActionSpec(
        "create_ark_deployment", "CreateArkDeployment", "POST", "InferenceService"
    ),
    ActionSpec(
        "create_basic_search_config_version",
        "CreateBasicSearchConfigVersion",
        "POST",
        "DataSource",
    ),
    ActionSpec("create_indexer", "CreateIndexer", "POST", "DataSource"),
    ActionSpec(
        "create_indexer_data_source", "CreateIndexerDataSource", "POST", "DataSource"
    ),
    ActionSpec("create_ml_api_" + "key", "CreateMLApi" + "Key", "POST", "Api" + "Key"),
    ActionSpec("create_psr_dataset", "CreatePsrDataset", "POST", "SceneDevelopment"),
    ActionSpec("create_psr_pipeline", "CreatePsrPipeline", "POST", "SceneDevelopment"),
    ActionSpec("create_psr_scene", "CreatePsrScene", "POST", "SceneDevelopment"),
    ActionSpec(
        "create_psr_serve_config", "CreatePsrServeConfig", "POST", "SceneDevelopment"
    ),
    ActionSpec("create_scene", "CreateScene", "POST", "Home,SceneDevelopment"),
    ActionSpec(
        "create_scene_version", "CreateSceneVersion", "POST", "SceneDevelopment"
    ),
    ActionSpec("create_search_config_v2", "CreateSearchConfigV2", "POST", "DataSource"),
    ActionSpec(
        "delete_ai_deployment", "DeleteAIDeployment", "POST", "InferenceService"
    ),
    ActionSpec("delete_ai_model", "DeleteAIModel", "POST", "ModelsManagement"),
    ActionSpec(
        "delete_ai_network",
        "DeleteAINetwork",
        "POST",
        "InferenceService,SceneDevelopment",
    ),
    ActionSpec("delete_agentic_chat", "DeleteAgenticChat", "POST", "SceneDevelopment"),
    ActionSpec(
        "delete_agentic_data_source",
        "DeleteAgenticDataSource",
        "POST",
        "AgenticDataSource",
    ),
    ActionSpec(
        "delete_agentic_data_source_scene_binding",
        "DeleteAgenticDataSourceSceneBinding",
        "POST",
        "SceneDevelopment",
    ),
    ActionSpec(
        "delete_agentic_scene", "DeleteAgenticScene", "POST", "SceneDevelopment"
    ),
    ActionSpec(
        "delete_agentic_skill", "DeleteAgenticSkill", "POST", "SceneDevelopment"
    ),
    ActionSpec("delete_agentic_tool", "DeleteAgenticTool", "POST", "SceneDevelopment"),
    ActionSpec("delete_agentic_user", "DeleteAgenticUser", "POST", "SceneDevelopment"),
    ActionSpec(
        "delete_agentic_variable", "DeleteAgenticVariable", "POST", "SceneDevelopment"
    ),
    ActionSpec(
        "delete_dataset_files", "DeleteDatasetFiles", "POST", "SceneDevelopment"
    ),
    ActionSpec("delete_indexer", "DeleteIndexer", "POST", "DataSource"),
    ActionSpec(
        "delete_indexer_data_source", "DeleteIndexerDataSource", "POST", "DataSource"
    ),
    ActionSpec("delete_ml_api_" + "key", "DeleteMLApi" + "Key", "POST", "Api" + "Key"),
    ActionSpec("delete_psr_dataset", "DeletePsrDataset", "POST", "SceneDevelopment"),
    ActionSpec("delete_psr_pipeline", "DeletePsrPipeline", "POST", "SceneDevelopment"),
    ActionSpec("delete_psr_scene", "DeletePsrScene", "POST", "SceneDevelopment"),
    ActionSpec("delete_psr_serve", "DeletePsrServe", "POST", "SceneDevelopment"),
    ActionSpec("delete_scene", "DeleteScene", "POST", "SceneDevelopment"),
    ActionSpec(
        "delete_scene_version", "DeleteSceneVersion", "POST", "SceneDevelopment"
    ),
    ActionSpec("delete_search_config_v2", "DeleteSearchConfigV2", "POST", "DataSource"),
    ActionSpec(
        "delete_search_config_version",
        "DeleteSearchConfigVersion",
        "POST",
        "DataSource",
    ),
    ActionSpec(
        "deploy_builtin_deployment",
        "DeployBuiltinDeployment",
        "POST",
        "InferenceService",
    ),
    ActionSpec(
        "describe_ai_network",
        "DescribeAINetwork",
        "POST",
        "InferenceService,SceneDevelopment",
    ),
    ActionSpec(
        "describe_ark_endpoint_price",
        "DescribeArkEndpointPrice",
        "POST",
        "InferenceService",
    ),
    ActionSpec(
        "describe_instance_price_v2",
        "DescribeInstancePriceV2",
        "POST",
        "InferenceService,SceneDevelopment",
    ),
    ActionSpec("describe_subnets", "DescribeSubnets", "POST", "SceneDevelopment"),
    ActionSpec(
        "describe_zones",
        "DescribeZones",
        "POST",
        "InferenceService,NodeForm,SceneDevelopment",
    ),
    ActionSpec(
        "edit_deployment_tag",
        "EditDeploymentTag",
        "POST",
        "InferenceService,SceneDevelopment",
    ),
    ActionSpec("exist_search_config_v2", "ExistSearchConfigV2", "GET", "DataSource"),
    ActionSpec(
        "fetch_dataset_example_data",
        "FetchDatasetExampleData",
        "GET",
        "SceneDevelopment",
    ),
    ActionSpec(
        "fetch_dataset_file_example_data",
        "FetchDatasetFileExampleData",
        "GET",
        "SceneDevelopment",
    ),
    ActionSpec(
        "fetch_schema_field_properties",
        "FetchSchemaFieldProperties",
        "GET",
        "SceneDevelopment",
    ),
    ActionSpec("get_ai_authorization", "GetAIAuthorization", "GET", "DataSource"),
    ActionSpec(
        "get_ai_deployment",
        "GetAIDeployment",
        "POST",
        "DataSource,InferenceService,SceneDevelopment",
    ),
    ActionSpec(
        "get_ai_deployment_relations",
        "GetAIDeploymentRelations",
        "POST",
        "InferenceService",
    ),
    ActionSpec(
        "get_ai_instance_spec",
        "GetAIInstanceSpec",
        "GET",
        "DataSource,InferenceService,SceneDevelopment",
    ),
    ActionSpec("get_ai_model", "GetAIModel", "POST", "ModelsManagement"),
    ActionSpec(
        "get_advanced_search_config_resource",
        "GetAdvancedSearchConfigResource",
        "GET",
        "DataSource",
    ),
    ActionSpec(
        "get_advanced_search_config_version",
        "GetAdvancedSearchConfigVersion",
        "GET",
        "DataSource",
    ),
    ActionSpec("get_agentic_chat", "GetAgenticChat", "GET", "SceneDevelopment"),
    ActionSpec(
        "get_agentic_chat_turn", "GetAgenticChatTurn", "GET", "SceneDevelopment"
    ),
    ActionSpec(
        "get_agentic_chat_turn_events",
        "GetAgenticChatTurnEvents",
        "GET",
        "SceneDevelopment",
    ),
    ActionSpec(
        "get_agentic_ctx_upload_info",
        "GetAgenticCtxUploadInfo",
        "POST",
        "SceneDevelopment",
    ),
    ActionSpec(
        "get_agentic_data_source", "GetAgenticDataSource", "POST", "SceneDevelopment"
    ),
    ActionSpec("get_agentic_scene", "GetAgenticScene", "GET", "SceneDevelopment"),
    ActionSpec(
        "get_agentic_skill_download_info",
        "GetAgenticSkillDownloadInfo",
        "GET",
        "SceneDevelopment",
    ),
    ActionSpec(
        "get_agentic_skill_file", "GetAgenticSkillFile", "GET", "SceneDevelopment"
    ),
    ActionSpec(
        "get_agentic_skill_upload_info",
        "GetAgenticSkillUploadInfo",
        "POST",
        "SceneDevelopment",
    ),
    ActionSpec(
        "get_ark_endpoint_usage", "GetArkEndpointUsage", "POST", "InferenceService"
    ),
    ActionSpec(
        "get_basic_search_config_resource",
        "GetBasicSearchConfigResource",
        "GET",
        "DataSource",
    ),
    ActionSpec(
        "get_basic_search_config_version",
        "GetBasicSearchConfigVersion",
        "GET",
        "DataSource",
    ),
    ActionSpec(
        "get_current_psr_serve", "GetCurrentPsrServe", "POST", "SceneDevelopment"
    ),
    ActionSpec(
        "get_gray_release_detail", "GetGrayReleaseDetail", "POST", "SceneDevelopment"
    ),
    ActionSpec("get_indexer", "GetIndexer", "GET", "DataSource"),
    ActionSpec("get_indexer_data_source", "GetIndexerDataSource", "GET", "DataSource"),
    ActionSpec("get_indexer_job", "GetIndexerJob", "GET", "DataSource"),
    ActionSpec(
        "get_indexer_upload_file_info",
        "GetIndexerUploadFileInfo",
        "POST",
        "DataSource,SceneDevelopment",
    ),
    ActionSpec("get_model_template", "GetModelTemplate", "GET", "SceneDevelopment"),
    ActionSpec("get_psr_dataset", "GetPsrDataset", "GET", "SceneDevelopment"),
    ActionSpec("get_psr_pipeline", "GetPsrPipeline", "GET", "SceneDevelopment"),
    ActionSpec(
        "get_psr_pipeline_runinstance",
        "GetPsrPipelineRuninstance",
        "GET",
        "SceneDevelopment",
    ),
    ActionSpec("get_psr_scene", "GetPsrScene", "GET", "SceneDevelopment"),
    ActionSpec("get_psr_serve", "GetPsrServe", "GET", "SceneDevelopment"),
    ActionSpec("get_scene", "GetScene", "GET", "SceneDevelopment"),
    ActionSpec("get_scene_data", "GetSceneData", "GET", "SceneDevelopment"),
    ActionSpec("get_scene_data_chunk", "GetSceneDataChunk", "GET", "SceneDevelopment"),
    ActionSpec(
        "get_scene_draft_version", "GetSceneDraftVersion", "GET", "SceneDevelopment"
    ),
    ActionSpec(
        "get_scene_ingest_config", "GetSceneIngestConfig", "GET", "SceneDevelopment"
    ),
    ActionSpec("get_scene_instance", "GetSceneInstance", "GET", "SceneDevelopment"),
    ActionSpec(
        "get_search_config_version_plugin_info",
        "GetSearchConfigVersionPluginInfo",
        "GET",
        "DataSource",
    ),
    ActionSpec("list_ai_deployment", "ListAIDeployment", "POST", "InferenceService"),
    ActionSpec("list_ai_model", "ListAIModel", "POST", "ModelsManagement"),
    ActionSpec(
        "list_agentic_chat_turns", "ListAgenticChatTurns", "GET", "SceneDevelopment"
    ),
    ActionSpec("list_agentic_chats", "ListAgenticChats", "GET", "SceneDevelopment"),
    ActionSpec(
        "list_agentic_data_source_scene_binding",
        "ListAgenticDataSourceSceneBinding",
        "POST",
        "SceneDevelopment",
    ),
    ActionSpec(
        "list_agentic_data_sources",
        "ListAgenticDataSources",
        "POST",
        "AgenticDataSource,SceneDevelopment",
    ),
    ActionSpec(
        "list_agentic_scene_template",
        "ListAgenticSceneTemplate",
        "GET",
        "SceneDevelopment",
    ),
    ActionSpec(
        "list_agentic_skill_files", "ListAgenticSkillFiles", "GET", "SceneDevelopment"
    ),
    ActionSpec("list_agentic_skills", "ListAgenticSkills", "GET", "SceneDevelopment"),
    ActionSpec("list_agentic_tools", "ListAgenticTools", "GET", "SceneDevelopment"),
    ActionSpec("list_agentic_users", "ListAgenticUsers", "POST", "SceneDevelopment"),
    ActionSpec(
        "list_agentic_variables", "ListAgenticVariables", "GET", "SceneDevelopment"
    ),
    ActionSpec("list_dataset_files", "ListDatasetFiles", "GET", "SceneDevelopment"),
    ActionSpec(
        "list_gray_release_history",
        "ListGrayReleaseHistory",
        "POST",
        "SceneDevelopment",
    ),
    ActionSpec("list_indexer", "ListIndexer", "GET", "DataSource"),
    ActionSpec(
        "list_indexer_data_source", "ListIndexerDataSource", "GET", "DataSource"
    ),
    ActionSpec(
        "list_indexer_data_source_by_vpc",
        "ListIndexerDataSourceByVpc",
        "GET",
        "DataSource,NodeForm",
    ),
    ActionSpec("list_indexer_file_meta", "ListIndexerFileMeta", "GET", "NodeForm"),
    ActionSpec("list_indexer_job", "ListIndexerJob", "GET", "DataSource"),
    ActionSpec("list_ml_api_keys", "ListMLApiKeys", "POST", "ApiKey"),
    ActionSpec(
        "list_model_rate_limit", "ListModelRateLimit", "POST", "InferenceService"
    ),
    ActionSpec("list_psr_dataset", "ListPsrDataset", "GET", "SceneDevelopment"),
    ActionSpec(
        "list_psr_pipeline_runs", "ListPsrPipelineRuns", "POST", "SceneDevelopment"
    ),
    ActionSpec("list_psr_pipelines", "ListPsrPipelines", "POST", "SceneDevelopment"),
    ActionSpec(
        "list_psr_serve_config_keys",
        "ListPsrServeConfigKeys",
        "GET",
        "SceneDevelopment",
    ),
    ActionSpec("list_scene", "ListScene", "GET", "Home,SceneDevelopment"),
    ActionSpec("list_scene_data", "ListSceneData", "GET", "SceneDevelopment"),
    ActionSpec(
        "list_scene_data_chunk", "ListSceneDataChunk", "GET", "SceneDevelopment"
    ),
    ActionSpec(
        "list_scene_template", "ListSceneTemplate", "GET", "Home,SceneDevelopment"
    ),
    ActionSpec("list_scene_version", "ListSceneVersion", "GET", "SceneDevelopment"),
    ActionSpec("list_search_config_v2", "ListSearchConfigV2", "GET", "DataSource"),
    ActionSpec(
        "list_search_config_version", "ListSearchConfigVersion", "GET", "DataSource"
    ),
    ActionSpec(
        "list_search_intervention_config",
        "ListSearchInterventionConfig",
        "GET",
        "DataSource",
    ),
    ActionSpec("modify_indexer", "ModifyIndexer", "POST", "DataSource"),
    ActionSpec("parse_schema", "ParseSchema", "POST", "SceneDevelopment"),
    ActionSpec("remove_scene_data", "RemoveSceneData", "POST", "SceneDevelopment"),
    ActionSpec(
        "restart_agentic_scene", "RestartAgenticScene", "POST", "SceneDevelopment"
    ),
    ActionSpec("restart_psr_scene", "RestartPsrScene", "POST", "SceneDevelopment"),
    ActionSpec("restart_psr_serve", "RestartPsrServe", "POST", "SceneDevelopment"),
    ActionSpec(
        "restart_scene_instance", "RestartSceneInstance", "POST", "SceneDevelopment"
    ),
    ActionSpec(
        "resume_agentic_scene", "ResumeAgenticScene", "POST", "SceneDevelopment"
    ),
    ActionSpec(
        "retry_agentic_chat_turn", "RetryAgenticChatTurn", "POST", "SceneDevelopment"
    ),
    ActionSpec(
        "rollback_gray_release", "RollbackGrayRelease", "POST", "SceneDevelopment"
    ),
    ActionSpec(
        "save_advanced_search_config_version",
        "SaveAdvancedSearchConfigVersion",
        "POST",
        "DataSource",
    ),
    ActionSpec(
        "send_agentic_chat_message",
        "SendAgenticChatMessage",
        "POST",
        "SceneDevelopment",
    ),
    ActionSpec("start_ai_deployment", "StartAIDeployment", "POST", "InferenceService"),
    ActionSpec("start_gray_release", "StartGrayRelease", "POST", "SceneDevelopment"),
    ActionSpec("start_indexer_job", "StartIndexerJob", "POST", "DataSource"),
    ActionSpec("start_psr_pipeline", "StartPsrPipeline", "POST", "SceneDevelopment"),
    ActionSpec("start_psr_serve", "StartPsrServe", "POST", "SceneDevelopment"),
    ActionSpec(
        "start_scene_instance", "StartSceneInstance", "POST", "SceneDevelopment"
    ),
    ActionSpec("stop_ai_deployment", "StopAIDeployment", "POST", "InferenceService"),
    ActionSpec("stop_agentic_scene", "StopAgenticScene", "POST", "SceneDevelopment"),
    ActionSpec("stop_indexer_job", "StopIndexerJob", "POST", "DataSource"),
    ActionSpec("stop_psr_pipeline", "StopPsrPipeline", "POST", "SceneDevelopment"),
    ActionSpec("stop_psr_scene", "StopPsrScene", "POST", "SceneDevelopment"),
    ActionSpec("stop_psr_serve", "StopPsrServe", "POST", "SceneDevelopment"),
    ActionSpec("stop_scene_instance", "StopSceneInstance", "POST", "SceneDevelopment"),
    ActionSpec(
        "test_scene_connection", "TestSceneConnection", "POST", "SceneDevelopment"
    ),
    ActionSpec(
        "test_search_config_version", "TestSearchConfigVersion", "POST", "DataSource"
    ),
    ActionSpec("trans_custom_config", "TransCustomConfig", "POST", "DataSource"),
    ActionSpec("trans_native_config", "TransNativeConfig", "POST", "DataSource"),
    ActionSpec(
        "update_ai_deployment", "UpdateAIDeployment", "POST", "InferenceService"
    ),
    ActionSpec("update_ai_model", "UpdateAIModel", "POST", "ModelsManagement"),
    ActionSpec(
        "update_agentic_data_source",
        "UpdateAgenticDataSource",
        "POST",
        "AgenticDataSource",
    ),
    ActionSpec(
        "update_agentic_scene", "UpdateAgenticScene", "POST", "SceneDevelopment"
    ),
    ActionSpec(
        "update_agentic_skill", "UpdateAgenticSkill", "POST", "SceneDevelopment"
    ),
    ActionSpec("update_agentic_tool", "UpdateAgenticTool", "POST", "SceneDevelopment"),
    ActionSpec(
        "update_agentic_variable", "UpdateAgenticVariable", "POST", "SceneDevelopment"
    ),
    ActionSpec(
        "update_basic_search_config_version",
        "UpdateBasicSearchConfigVersion",
        "POST",
        "DataSource",
    ),
    ActionSpec(
        "update_indexer_data_source", "UpdateIndexerDataSource", "POST", "DataSource"
    ),
    ActionSpec("update_ip_allowlist", "UpdateIpAllowlist", "POST", "SceneDevelopment"),
    ActionSpec("update_psr_dataset", "UpdatePsrDataset", "POST", "SceneDevelopment"),
    ActionSpec("update_psr_pipeline", "UpdatePsrPipeline", "POST", "SceneDevelopment"),
    ActionSpec("update_psr_scene", "UpdatePsrScene", "POST", "SceneDevelopment"),
    ActionSpec(
        "update_psr_serve_config", "UpdatePsrServeConfig", "POST", "SceneDevelopment"
    ),
    ActionSpec("update_scene", "UpdateScene", "POST", "SceneDevelopment"),
    ActionSpec(
        "update_scene_draft_version",
        "UpdateSceneDraftVersion",
        "POST",
        "SceneDevelopment",
    ),
    ActionSpec(
        "update_scene_instance", "UpdateSceneInstance", "POST", "SceneDevelopment"
    ),
    ActionSpec("update_search_config_v2", "UpdateSearchConfigV2", "POST", "DataSource"),
    ActionSpec(
        "update_search_intervention_config",
        "UpdateSearchInterventionConfig",
        "POST",
        "DataSource",
    ),
    ActionSpec("upgrade_scene", "UpgradeScene", "POST", "SceneDevelopment"),
    ActionSpec(
        "upload_agentic_ctx_file", "UploadAgenticCtxFile", "POST", "SceneDevelopment"
    ),
    ActionSpec(
        "upload_agentic_skill", "UploadAgenticSkill", "POST", "SceneDevelopment"
    ),
    ActionSpec(
        "upload_dataset_files", "UploadDatasetFiles", "POST", "SceneDevelopment"
    ),
]


SHORTCUT_FIELDS = [
    ("id", "Id"),
    ("scene_id", "SceneId"),
    ("scene_type", "SceneType"),
    ("project", "Project"),
    ("name", "Name"),
    ("version", "Version"),
    ("environment", "Environment"),
    ("data_id", "DataId"),
    ("data_source_id", "DataSourceId"),
    ("datasource_id", "DatasourceId"),
    ("model_id", "ModelId"),
    ("deployment_id", "DeploymentId"),
    ("serve_config_id", "ServeConfigId"),
    ("job_id", "JobId"),
    ("pipeline_id", "PipelineId"),
    ("run_id", "RunId"),
    ("chat_id", "ChatId"),
    ("turn_id", "TurnId"),
    ("skill_id", "SkillId"),
    ("tool_id", "ToolId"),
    ("variable_id", "VariableId"),
    ("user_id", "UserId"),
    ("page_num", "PageNum"),
    ("page_number", "PageNumber"),
    ("page_size", "PageSize"),
    ("es_instance_id", "EsInstanceId"),
    ("search_config_name", "SearchConfigName"),
    ("index_name", "IndexName"),
    ("index_name_key", "IndexNameKey"),
    ("index_template_name", "IndexTemplateName"),
    ("index_template_name_key", "IndexTemplateNameKey"),
    ("is_demo", "IsDemo"),
    ("is_default", "IsDefault"),
]

CONFIRMATION_FIELDS = (
    "Id",
    "SceneId",
    "DataId",
    "DataSourceId",
    "DatasourceId",
    "ModelId",
    "DeploymentId",
    "ServeConfigId",
    "JobId",
    "PipelineId",
    "RunId",
    "ChatId",
    "TurnId",
    "SkillId",
    "ToolId",
    "VariableId",
    "UserId",
)


def _add_shortcut_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--body-json", default="", help="业务请求体 JSON 对象；复杂表单推荐使用该参数"
    )
    parser.add_argument(
        "--body-file",
        default="",
        help="业务请求体 JSON 文件路径；与 --body-json 二选一",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="只打印 action/method/body，不发起请求"
    )
    parser.add_argument(
        "--confirm",
        nargs="?",
        const=True,
        default=False,
        help="删除类动作必须显式提供；推荐值与目标 ID 一致",
    )
    parser.add_argument("--id", default=None, help="快捷写入请求体 Id")
    parser.add_argument(
        "--scene-id", dest="scene_id", default=None, help="快捷写入请求体 SceneId"
    )
    parser.add_argument(
        "--scene-type", dest="scene_type", default=None, help="快捷写入请求体 SceneType"
    )
    parser.add_argument("--project", default=None, help="快捷写入请求体 Project")
    parser.add_argument("--name", default=None, help="快捷写入请求体 Name")
    parser.add_argument("--version", default=None, help="快捷写入请求体 Version")
    parser.add_argument(
        "--environment", default=None, help="快捷写入请求体 Environment"
    )
    parser.add_argument(
        "--data-id", dest="data_id", default=None, help="快捷写入请求体 DataId"
    )
    parser.add_argument(
        "--data-source-id",
        dest="data_source_id",
        default=None,
        help="快捷写入请求体 DataSourceId",
    )
    parser.add_argument(
        "--datasource-id",
        dest="datasource_id",
        default=None,
        help="快捷写入请求体 DatasourceId",
    )
    parser.add_argument(
        "--model-id", dest="model_id", default=None, help="快捷写入请求体 ModelId"
    )
    parser.add_argument(
        "--deployment-id",
        dest="deployment_id",
        default=None,
        help="快捷写入请求体 DeploymentId",
    )
    parser.add_argument(
        "--serve-config-id",
        dest="serve_config_id",
        default=None,
        help="快捷写入请求体 ServeConfigId",
    )
    parser.add_argument(
        "--job-id", dest="job_id", default=None, help="快捷写入请求体 JobId"
    )
    parser.add_argument(
        "--pipeline-id",
        dest="pipeline_id",
        default=None,
        help="快捷写入请求体 PipelineId",
    )
    parser.add_argument(
        "--run-id", dest="run_id", default=None, help="快捷写入请求体 RunId"
    )
    parser.add_argument(
        "--chat-id", dest="chat_id", default=None, help="快捷写入请求体 ChatId"
    )
    parser.add_argument(
        "--turn-id", dest="turn_id", default=None, help="快捷写入请求体 TurnId"
    )
    parser.add_argument(
        "--skill-id", dest="skill_id", default=None, help="快捷写入请求体 SkillId"
    )
    parser.add_argument(
        "--tool-id", dest="tool_id", default=None, help="快捷写入请求体 ToolId"
    )
    parser.add_argument(
        "--variable-id",
        dest="variable_id",
        default=None,
        help="快捷写入请求体 VariableId",
    )
    parser.add_argument(
        "--user-id", dest="user_id", default=None, help="快捷写入请求体 UserId"
    )
    parser.add_argument(
        "--page-num",
        dest="page_num",
        type=int,
        default=None,
        help="快捷写入请求体 PageNum",
    )
    parser.add_argument(
        "--page-number",
        dest="page_number",
        type=int,
        default=None,
        help="快捷写入请求体 PageNumber",
    )
    parser.add_argument(
        "--page-size",
        dest="page_size",
        type=int,
        default=None,
        help="快捷写入请求体 PageSize",
    )
    parser.add_argument(
        "--es-instance-id",
        dest="es_instance_id",
        default=None,
        help="快捷写入请求体 EsInstanceId",
    )
    parser.add_argument(
        "--search-config-name",
        dest="search_config_name",
        default=None,
        help="快捷写入请求体 SearchConfigName",
    )
    parser.add_argument(
        "--index-name", dest="index_name", default=None, help="快捷写入请求体 IndexName"
    )
    parser.add_argument(
        "--index-name-key",
        dest="index_name_key",
        default=None,
        help="快捷写入请求体 IndexNameKey",
    )
    parser.add_argument(
        "--index-template-name",
        dest="index_template_name",
        default=None,
        help="快捷写入请求体 IndexTemplateName",
    )
    parser.add_argument(
        "--index-template-name-key",
        dest="index_template_name_key",
        default=None,
        help="快捷写入请求体 IndexTemplateNameKey",
    )
    parser.add_argument(
        "--is-demo",
        dest="is_demo",
        action="store_const",
        const=True,
        default=None,
        help="快捷写入请求体 IsDemo=true",
    )
    parser.add_argument(
        "--is-default",
        dest="is_default",
        action="store_const",
        const=True,
        default=None,
        help="快捷写入请求体 IsDefault=true",
    )


def _build_payload(args: argparse.Namespace) -> dict:
    payload = parse_json_payload(args.body_json, args.body_file)
    for attr, key in SHORTCUT_FIELDS:
        value = getattr(args, attr, None)
        if value is not None:
            payload[key] = value
    return payload


def _payload_confirmation_values(body: dict) -> List[str]:
    values = []
    for key in CONFIRMATION_FIELDS:
        value = body.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            values.extend(str(item) for item in value if item is not None)
        else:
            values.append(str(value))
    return values


def cmd_console_action(args: argparse.Namespace) -> None:
    spec = args.action_spec
    body = _build_payload(args)
    if spec.command.startswith("delete_"):
        if not args.confirm:
            print_error(
                "Confirmation Required",
                f"Refusing to run {spec.action} without --confirm.",
            )
        if isinstance(args.confirm, str):
            expected_values = _payload_confirmation_values(body)
            if expected_values and args.confirm not in expected_values:
                print_error(
                    "Confirmation Mismatch",
                    "--confirm must match the target id: %s"
                    % ", ".join(expected_values),
                )

    if args.dry_run:
        print_result(
            {
                "action": spec.action,
                "method": spec.method,
                "service": "ctxsearch",
                "version": "2025-09-01",
                "body": body,
            }
        )
        return

    universal_call(action=spec.action, body=body, method=spec.method)


def cmd_console_list(args: argparse.Namespace) -> None:
    items = [
        {
            "command": spec.command,
            "action": spec.action,
            "method": spec.method,
            "pages": spec.pages,
        }
        for spec in CONSOLE_ACTIONS
    ]
    print_result(items)


def register_console(ns_parsers: Any) -> None:
    """Register one CLI subcommand for every ContextSearch console action."""
    console_parser = ns_parsers.add_parser(
        "console",
        help="ContextSearch 控制台操作 action 命令集",
    )
    subparsers = console_parser.add_subparsers(dest="command", required=True)

    p_list = subparsers.add_parser("list", help="列出当前已注册的全部控制台 action")
    p_list.set_defaults(func=cmd_console_list)

    for spec in CONSOLE_ACTIONS:
        parser = subparsers.add_parser(
            spec.command,
            help=f"{spec.action} ({spec.method}) in {spec.pages}",
        )
        _add_shortcut_args(parser)
        parser.set_defaults(func=cmd_console_action, action_spec=spec)
