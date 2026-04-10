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
"""
get_media_info.py — 获取媒资信息（含播放地址）

用法：
  python get_media_info.py '{"vids":"v001,v002"}'
  python get_media_info.py @params.json

参数：
  vids (str, 必需): 逗号分隔的 Vid 列表

返回：
  每个 Vid 的基础信息、片源信息及播放链接
"""
import sys, os, json

sys.path.insert(0, os.path.dirname(__file__))
from vod_common import init_and_parse, log, out, bail
from api_manage import ApiManage

# GetMediaInfos 接口单次最多 20 个 Vid
BATCH_LIMIT = 20


def _fetch_batch(api: ApiManage, vids_str: str, space_name: str) -> dict:
    """单次请求最多 20 个 vid。"""
    raw = api.get_media_infos(vids_str, space_name)
    if isinstance(raw, str):
        raw = json.loads(raw)
    return raw.get("Result", raw)


def run(api: ApiManage, args: dict, space_name: str):
    vids_raw = args.get("vids") or args.get("Vids") or ""
    if not vids_raw:
        return {"error": "缺少必需参数 vids（逗号分隔的 Vid 列表）"}

    # 统一为列表
    if isinstance(vids_raw, list):
        vid_list = [v.strip() for v in vids_raw if v.strip()]
    else:
        vid_list = [v.strip() for v in str(vids_raw).split(",") if v.strip()]

    if not vid_list:
        return {"error": "vids 为空"}

    all_media = []
    not_exist = []

    # 分批请求，每批最多 BATCH_LIMIT 个
    for i in range(0, len(vid_list), BATCH_LIMIT):
        batch = vid_list[i : i + BATCH_LIMIT]
        batch_str = ",".join(batch)
        log(f"查询媒资信息 [{i+1}~{i+len(batch)}/{len(vid_list)}]: {batch_str}")

        result = _fetch_batch(api, batch_str, space_name)
        media_list = result.get("MediaInfoList") or []
        batch_not_exist = result.get("NotExistVids") or []
        not_exist.extend(batch_not_exist)

        for item in media_list:
            basic = item.get("BasicInfo", {})
            source = item.get("SourceInfo", {})
            vid = basic.get("Vid", "")

            # 获取播放地址
            play_url = ""
            if vid:
                try:
                    info = api.get_play_video_info(vid, space_name)
                    play_url = info.get("PlayURL", "")
                except Exception as e:
                    log(f"获取播放地址失败 ({vid}): {e}")
                    # 降级：通过 FileName 获取
                    fname = source.get("FileName", "")
                    if fname:
                        try:
                            play_url = api.get_play_url("directurl", fname, space_name)
                        except Exception:
                            pass

            all_media.append({
                "Vid": vid,
                "Title": basic.get("Title", ""),
                "SpaceName": basic.get("SpaceName", ""),
                "PublishStatus": basic.get("PublishStatus", ""),
                "CreateTime": basic.get("CreateTime", ""),
                "Source": {
                    "Format": source.get("Format", ""),
                    "Duration": source.get("Duration"),
                    "Width": source.get("Width"),
                    "Height": source.get("Height"),
                    "Size": source.get("Size"),
                    "Codec": source.get("Codec", ""),
                    "Fps": source.get("Fps"),
                    "FileName": source.get("FileName", ""),
                },
                "PlayUrl": play_url,
            })

    output = {"MediaInfoList": all_media}
    if not_exist:
        output["NotExistVids"] = not_exist

    return output


def main():
    api, space_name, args = init_and_parse()
    result = run(api, args, space_name)
    out(result)


if __name__ == "__main__":
    main()
