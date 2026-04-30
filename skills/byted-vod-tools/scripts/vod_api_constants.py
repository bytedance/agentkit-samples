#!/usr/bin/env python3
# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# --- VOD Action names (must match OpenAPI Action parameter) ---
VOD_ACTION_LIST_SPACE = "ListSpace"
VOD_ACTION_UPLOAD_MEDIA_BY_URL = "UploadMediaByUrl"
VOD_ACTION_QUERY_UPLOAD_TASK_INFO = "QueryUploadTaskInfo"
# AI 视频智剪：异步提交 / 查询结果（文档见火山 VOD OpenAPI）
VOD_ACTION_SUBMIT_ASYNC_AI_CLIP = "AsyncVCreativeTask"
VOD_ACTION_GET_AI_CLIP_TASK_RESULT = "GetVCreativeTaskResult"
VOD_FIELD_AI_CLIP_TASK_ID = "VCreativeId"
VOD_ACTION_GET_VIDEO_PLAY_INFO = "GetVideoPlayInfo"
VOD_ACTION_UPDATE_MEDIA_PUBLISH_STATUS = "UpdateMediaPublishStatus"
VOD_ACTION_START_EXECUTION = "StartExecution"
VOD_ACTION_GET_EXECUTION = "GetExecution"
VOD_ACTION_LIST_DOMAIN = "ListDomain"
VOD_ACTION_DESCRIBE_DOMAIN_CONFIG = "DescribeDomainConfig"
VOD_ACTION_GET_STORAGE_CONFIG = "GetStorageConfig"
VOD_ACTION_APPLY_UPLOAD_INFO = "ApplyUploadInfo"
VOD_ACTION_COMMIT_UPLOAD_INFO = "CommitUploadInfo"

# --- AI 视频翻译 ---
VOD_ACTION_SUBMIT_AI_TRANSLATION_WORKFLOW = "SubmitAITranslationWorkflow"
VOD_ACTION_GET_AI_TRANSLATION_PROJECT = "GetAITranslationProject"
VOD_ACTION_LIST_AI_TRANSLATION_PROJECT = "ListAITranslationProject"

# --- AI 解说视频生成 ---
VOD_ACTION_CREATE_DRAMA_RECAP_TASK = "CreateDramaRecapTask"
VOD_ACTION_QUERY_DRAMA_RECAP_TASK = "QueryDramaRecapTask"

# --- AI 剧本还原 ---
VOD_ACTION_CREATE_DRAMA_SCRIPT_TASK = "CreateDramaScriptTask"
VOD_ACTION_QUERY_DRAMA_SCRIPT_TASK = "QueryDramaScriptTask"

# --- 媒资信息查询 ---
VOD_ACTION_GET_MEDIA_INFOS = "GetMediaInfos"
