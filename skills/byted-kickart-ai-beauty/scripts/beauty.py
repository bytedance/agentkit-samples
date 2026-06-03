# MIT License
# 
# Copyright (c) 2026 ByteDance
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import click
import logging
import sys
import time
import json
import os
import zipfile
import tarfile
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

from core import Result
from core.api.iccp.service import IccpService
from core.api.meida.media import MuseRemoteUploader

AI_BEAUTY_SERVICE_ID = 2456212295650178


from core.utils.validator import DefaultValidator


def get_image_url(file_input):
    """
    获取图片URL，支持本地文件或URL
    
    Args:
        file_input: 文件路径或URL
        
    Returns:
        image_url: 图片URL
    """
    if file_input.startswith('http://') or file_input.startswith('https://'):
        # 对于 URL，先下载到临时文件进行校验
        import tempfile
        
        # 创建一个临时文件
        fd, temp_path = tempfile.mkstemp(suffix='.jpg')
        os.close(fd)
        
        try:
            # 复用已有的 download_image 方法下载图片
            success = download_image(file_input, temp_path)
            if not success:
                raise ValueError(f"图片下载失败，请检查URL是否有效")
            
            # 进行图片 size 校验
            val_result = DefaultValidator.validate(temp_path)
            if not val_result.get("valid"):
                err_msgs = "; ".join(val_result.get("errors", []))
                raise ValueError(f"图片校验失败: {err_msgs}")
                
            return file_input
        except Exception as e:
            if isinstance(e, ValueError):
                raise e
            raise ValueError(f"下载或校验URL图片失败: {str(e)}")
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
    else:
        if not os.path.isfile(file_input):
            raise ValueError(f"文件不存在: {file_input}")
            
        # 进行图片 size 校验
        val_result = DefaultValidator.validate(file_input)
        if not val_result.get("valid"):
            err_msgs = "; ".join(val_result.get("errors", []))
            raise ValueError(f"图片校验失败: {err_msgs}")
            
        uploader = MuseRemoteUploader()
        material = uploader.upload(file_input)
        return material.url


def wait_for_task_completion(iccp_service, task_id):
    """
    轮询等待任务完成
    
    Args:
        iccp_service: ICCP服务实例
        task_id: 任务ID
        
    Returns:
        Result: 包含 code, message 的 Result 对象
            - code: "0" 表示成功；其他错误码直接沿用 iccp_service.query 返回的错误码；
                    "-1" 表示解析任务结果失败；"-2" 表示任务超时
            - message: 成功时是美化后的图片链接，失败时是错误原因
    """
    for _ in range(2 * 5):
        time.sleep(30)
        poll_res = iccp_service.query(task_id)

        if poll_res.code == "1000": 
            continue
        if poll_res.code != "0": 
            return Result(
                code=poll_res.code,
                message=poll_res.message
            )
        
        try:
            result_data = json.loads(poll_res.message)
            return Result(
                code="0",
                message=result_data.get("result_url", "")
            )
        except Exception as e:
            return Result(
                code="-1",
                message=f"解析任务结果失败: {str(e)}"
            )
    
    return Result(
        code="-2",
        message=f"任务超时，请通过任务ID:{task_id}查询任务状态"
    )


def process_single_image(file_input, iccp_service=None, uploader=None):
    """
    处理单张图片
    
    Args:
        file_input: 图片路径或URL
        iccp_service: ICCP服务实例（可选，用于复用）
        uploader: 上传器实例（可选，用于复用）
        
    Returns:
        result: 处理结果字典
            - 成功: {"image_name": "...", "result_url": "..."}
            - 失败: {"image_name": "...", "error_code": "...", "error_msg": "..."}
    """
    try:
        # 获取原始文件名
        if file_input.startswith('http'):
            image_name = file_input.split('/')[-1].split('?')[0] or f"image_{int(time.time())}.jpg"
        else:
            image_name = os.path.basename(file_input)
        
        image_url = get_image_url(file_input)
        body = json.dumps({
            "beautyToolConfigKey": "beautyPro_481"
        }, ensure_ascii=False)

        if iccp_service is None:
            iccp_service = IccpService()

        submit_res = iccp_service.submit(AI_BEAUTY_SERVICE_ID, image_url, body)
        click.echo(submit_res.model_dump_json())
        if submit_res.code != "0": 
            return {
                "image_name": image_name,
                "error_code": submit_res.code,
                "error_msg": f"任务提交失败: {submit_res.message}"
            }
        click.echo(f"提交任务成功，任务ID: {submit_res.message}")

        result = wait_for_task_completion(iccp_service, submit_res.message)
        if result.code == "0":
            return {
                "image_name": image_name,
                "result_url": result.message
            }
        else:
            return {
                "image_name": image_name,
                "error_code": result.code,
                "error_msg": result.message
            }
    except Exception as e:
        error_msg = str(e)
        click.echo(f"处理图片失败 {file_input}: {error_msg}", err=True)
        
        # 获取原始文件名（即使失败也需要）
        if file_input.startswith('http'):
            image_name = file_input.split('/')[-1].split('?')[0] or f"image_{int(time.time())}.jpg"
        else:
            image_name = os.path.basename(file_input)
        
        return {
            "image_name": image_name,
            "error_code": "-999",
            "error_msg": error_msg
        }


def process_single_image_task(item, index, total, output_dir):
    """
    处理单张图片的任务函数（用于并发）
    
    Args:
        item: 图片路径或URL
        index: 图片索引
        total: 总图片数
        output_dir: 输出目录
        
    Returns:
        result: 处理结果字典
            - 成功: {"image_name": "...", "result_url": "...", "success": True}
            - 失败: {"image_name": "...", "error_code": "...", "error_msg": "...", "success": False}
    """
    # 增加随机延迟，避免所有线程同时发起请求导致服务端并发限制(触发1400等异常)
    import random
    time.sleep(random.uniform(0.1, 1.0))
    
    max_retries = 2
    retry_delay = 3
    
    for attempt in range(max_retries + 1):
        try:
            item_str = item[:60] + "..." if len(item) > 60 else item
            click.echo(f"[并发] 正在处理第 {index}/{total} 张(尝试 {attempt+1}/{max_retries+1}): {item_str}")
            
            # 获取原始文件名
            if item.startswith('http'):
                image_name = item.split('/')[-1].split('?')[0] or f"image_{index}.jpg"
            else:
                image_name = os.path.basename(item)
            
            image_url = get_image_url(item)
            
            # 防御性检查：确保image_url不为空
            if not image_url or not isinstance(image_url, str) or len(image_url.strip()) == 0:
                error_msg = f"图片URL为空或无效: {image_url}"
                click.echo(f"[并发] 第 {index}/{total} 张 {error_msg}")
                return {
                    "image_name": image_name,
                    "success": False,
                    "error_code": "-100",
                    "error_msg": error_msg
                }
            
            body = json.dumps({
                "beautyToolConfigKey": "beautyPro_481"
            }, ensure_ascii=False)

            # 每次请求新建服务实例，避免多线程复用同一个实例产生状态混乱
            iccp_service = IccpService()
            submit_res = iccp_service.submit(AI_BEAUTY_SERVICE_ID, image_url, body)
            
            if submit_res.code != "0": 
                # 针对 1400 (参数错误/缺失，可能是服务端并发限制导致) 进行重试
                if submit_res.code == "1400" and attempt < max_retries:
                    click.echo(f"[并发] 第 {index}/{total} 张提交失败，准备重试: {submit_res.message}")
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                    
                error_msg = f"提交失败: {submit_res.message}"
                click.echo(f"[并发] 第 {index}/{total} 张 {error_msg}")
                return {
                    "image_name": image_name,
                    "success": False,
                    "error_code": submit_res.code,
                    "error_msg": error_msg
                }
            
            task_id = submit_res.message
            click.echo(f"[并发] 第 {index}/{total} 张提交成功，任务ID: {task_id}")

            result = wait_for_task_completion(iccp_service, task_id)
            if result.code == "0":
                # 下载美颜后的图片
                result_url = result.message
                if not image_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                    image_name = f"image_{index}.jpg"
                output_img_path = os.path.join(output_dir, f"beauty_{image_name}")
                if output_img_path.lower().endswith('.png'):
                    output_img_path = output_img_path[:-4] + '.jpg'
                download_image(result_url, output_img_path)
                
                return {
                    "image_name": image_name,
                    "success": True,
                    "result_url": result_url
                }
            else:
                # 针对轮询阶段返回的 1400 错误也进行重试
                if result.code == "1400" and attempt < max_retries:
                    click.echo(f"[并发] 第 {index}/{total} 张任务轮询失败，准备重试: {result.message}")
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                    
                return {
                    "image_name": image_name,
                    "success": False,
                    "error_code": result.code,
                    "error_msg": result.message
                }
        except BaseException as e:
            error_msg = str(e)
            if not error_msg and isinstance(e, SystemExit):
                error_msg = "组件内部退出(SystemExit)"
            click.echo(f"[并发] 处理第 {index}/{total} 张失败(尝试 {attempt+1}/{max_retries+1}): {type(e).__name__} - {error_msg}", err=True)
            
            # 对系统异常也进行重试
            if attempt < max_retries:
                time.sleep(retry_delay * (attempt + 1))
                continue
                
            # 获取原始文件名（即使失败也需要）
            if item.startswith('http'):
                image_name = item.split('/')[-1].split('?')[0] or f"image_{index}.jpg"
            else:
                image_name = os.path.basename(item)
            
            return {
                "image_name": image_name,
                "success": False,
                "error_code": "-999",
                "error_msg": error_msg
            }


def extract_archive_file(archive_file, extract_dir):
    """
    解压压缩包（支持 zip, tar, tar.gz, tar.bz2 格式）
    
    Args:
        archive_file: 压缩包文件路径
        extract_dir: 解压目录
        
    Returns:
        success: 是否成功
    """
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
    os.makedirs(extract_dir, exist_ok=True)
    
    # 常见的非 UTF-8 编码列表（按优先级尝试）
    common_encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'shift_jis', 'euc_kr']
    
    file_lower = archive_file.lower()
    try:
        if file_lower.endswith('.zip'):
            with zipfile.ZipFile(archive_file, 'r') as zip_ref:
                extract_dir_real = os.path.realpath(extract_dir) + os.sep
                for member in zip_ref.infolist():
                    # 检查 ZIP 通用比特标志第 11 位是否为 1 (表示 UTF-8 编码)
                    is_utf8 = (member.flag_bits & 0x800) != 0
                    
                    filename = member.filename
                    if not is_utf8:
                        # 如果不是 UTF-8 标记，zipfile 会错误地用 cp437 解码。我们将其还原为原始字节
                        try:
                            raw_bytes = filename.encode('cp437')
                            # 尝试使用常见编码进行解码
                            for enc in common_encodings:
                                try:
                                    filename = raw_bytes.decode(enc)
                                    break
                                except UnicodeDecodeError:
                                    continue
                        except Exception:
                            pass # 还原原始字节失败则保持原样
                    
                    member_path = os.path.join(extract_dir, filename)
                    if not os.path.realpath(member_path).startswith(extract_dir_real):
                        raise ValueError(f"压缩包包含非法路径: {filename}")
                    
                    # 确保目标目录存在
                    if member.is_dir():
                        os.makedirs(member_path, exist_ok=True)
                        continue
                        
                    os.makedirs(os.path.dirname(member_path), exist_ok=True)
                    
                    # 写入文件
                    with zip_ref.open(member) as source, open(member_path, 'wb') as target:
                        shutil.copyfileobj(source, target)
            return True
        elif file_lower.endswith(('.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2', '.tar.xz', '.txz')):
            with tarfile.open(archive_file, 'r:*') as tar_ref:
                extract_dir_real = os.path.realpath(extract_dir) + os.sep
                for member in tar_ref.getmembers():
                    # tarfile 中文件名编码问题处理
                    filename = member.name
                    if isinstance(member.name, bytes):
                        for enc in common_encodings:
                            try:
                                filename = member.name.decode(enc)
                                break
                            except UnicodeDecodeError:
                                continue
                                
                    member_path = os.path.join(extract_dir, filename)
                    if not os.path.realpath(member_path).startswith(extract_dir_real):
                        raise ValueError(f"压缩包包含非法路径: {filename}")
                        
                    # 更新 member 的 name 属性，确保 extract 时使用修正后的名称
                    original_name = member.name
                    member.name = filename
                    try:
                        tar_ref.extract(member, extract_dir)
                    finally:
                        member.name = original_name
            return True
        else:
            click.echo(Result(code="-1", message=f"不支持的压缩格式: {archive_file}"), err=True)
            return False
    except Exception as e:
        click.echo(Result(code="-1", message=f"解压失败: {str(e)}"), err=True)
        return False


def get_image_files_from_dir(dir_path):
    """
    从目录中获取所有支持的图片文件
    
    Args:
        dir_path: 目录路径
        
    Returns:
        image_files: 图片文件路径列表
    """
    supported_exts = ('.jpg', '.jpeg', '.png', '.webp')
    image_files = []
    for root, dirs, files in os.walk(dir_path):
        for f in files:
            if f.lower().endswith(supported_exts) and not f.startswith('._'):
                image_files.append(os.path.join(root, f))
    return image_files


def download_image(url, output_path):
    """
    下载图片
    
    Args:
        url: 图片URL
        output_path: 输出路径
        
    Returns:
        success: 是否成功
    """
    try:
        import urllib.parse
        import urllib.request
        
        # 对 URL 中的路径部分进行正确的编码，处理中文等非 ASCII 字符
        parsed_url = urllib.parse.urlparse(url)
        # 对路径部分单独进行 quote，保留域名等其他部分的原样
        quoted_path = urllib.parse.quote(parsed_url.path, safe='/')
        # 重新拼接 URL
        encoded_url = urllib.parse.urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            quoted_path,
            parsed_url.params,
            parsed_url.query,
            parsed_url.fragment
        ))
        
        # 添加 User-Agent 头，避免被部分服务器拒绝
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        req = urllib.request.Request(encoded_url, headers=headers)
        
        with urllib.request.urlopen(req) as response, open(output_path, 'wb') as out_file:
            out_file.write(response.read())
            
        click.echo(f"已下载: {output_path}")
        return True
    except Exception as e:
        click.echo(f"下载失败: {str(e)}")
        return False


def create_zip_from_dir(source_dir, output_zip):
    """
    从目录创建zip文件
    
    Args:
        source_dir: 源目录
        output_zip: 输出zip路径
    """
    try:
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_dir):
                for f in files:
                    if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                        file_path = os.path.join(root, f)
                        zipf.write(file_path, os.path.basename(file_path))
        click.echo(f"批量处理完成，所有美颜后图片已打包到: {output_zip}")
    except Exception as e:
        click.echo(f"打包zip失败: {str(e)}")


def process_multiple_urls(url_list, output, max_workers=5):
    """
    批量处理多张图片URL（并发处理）
    
    Args:
        url_list: 图片URL列表
        output: 输出JSON文件路径
        max_workers: 最大并发数，默认5
    """
    output_dir = "/tmp/ai_beauty_batch_output"
    # 清理临时目录，避免历史文件累积
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)

    os.makedirs(output_dir, exist_ok=True)
    
    # 过滤掉空URL
    valid_urls = [url.strip() for url in url_list if url.strip()]
    total = len(valid_urls)
    
    if total == 0:
        click.echo(Result(code="-1", message="没有有效的图片URL"), err=True)
        exit(1)
    
    click.echo(f"开始并发处理 {total} 张图片，最大并发数: {max_workers}")
    
    # 并发处理图片
    all_results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        futures = []
        for i, url in enumerate(valid_urls, 1):
            futures.append(executor.submit(
                process_single_image_task, url, i, total, output_dir
            ))
        
        # 收集结果
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_results.append(result)
    
    # 区分成功和失败结果
    success_results = [r for r in all_results if r.get("success")]
    failed_results = [r for r in all_results if not r.get("success")]
    
    click.echo(f"并发处理完成，成功处理 {len(success_results)}/{total} 张图片")
    if failed_results:
        click.echo(f"失败 {len(failed_results)} 张图片:")
        for r in failed_results:
            click.echo(f"  - {r['image_name']}: {r.get('error_msg', '未知错误')}")
    
    # 打包处理好的图片
    zip_output_path = output.replace('.json', '.zip')
    create_zip_from_dir(output_dir, zip_output_path)
    
    # 保存结果（同时包含成功和失败信息）
    with open(output, "w") as f:
        json.dump({
            "success_count": len(success_results),
            "failed_count": len(failed_results),
            "total_count": total,
            "results": all_results,
            "zip_path": zip_output_path
        }, f, ensure_ascii=False, indent=2)
    click.echo(Result(code="0", message=output).model_dump_json())


def process_archive_file(archive_file, output, max_workers=5):
    """
    批量处理压缩包中的图片（支持 zip, tar, tar.gz, tar.bz2 格式，并发处理）
    
    Args:
        archive_file: 压缩包文件路径
        output: 输出JSON文件路径
        max_workers: 最大并发数，默认5
    """
    output_dir = "/tmp/ai_beauty_batch_output"
    extract_dir = "/tmp/ai_beauty_extract"

    # 清理临时目录，避免历史文件累积
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)

    os.makedirs(output_dir, exist_ok=True)
    
    # 解压压缩包
    if not extract_archive_file(archive_file, extract_dir):
        exit(1)
    
    # 获取图片文件
    image_files = get_image_files_from_dir(extract_dir)
    total = len(image_files)
    if total == 0:
        click.echo(Result(code="-1", message="压缩包中未找到支持的图片文件"), err=True)
        exit(1)
    
    click.echo(f"开始并发处理 {total} 张图片，最大并发数: {max_workers}")
    
    # 并发处理图片
    all_results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        futures = []
        for i, img_path in enumerate(image_files, 1):
            futures.append(executor.submit(
                process_single_image_task, img_path, i, total, output_dir
            ))
        
        # 收集结果
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_results.append(result)
    
    # 区分成功和失败结果
    success_results = [r for r in all_results if r.get("success")]
    failed_results = [r for r in all_results if not r.get("success")]
    
    click.echo(f"并发处理完成，成功处理 {len(success_results)}/{total} 张图片")
    if failed_results:
        click.echo(f"失败 {len(failed_results)} 张图片:")
        for r in failed_results:
            click.echo(f"  - {r['image_name']}: {r.get('error_msg', '未知错误')}")
    
    # 打包处理好的图片
    zip_output_path = output.replace('.json', '.zip')
    create_zip_from_dir(output_dir, zip_output_path)
    
    # 保存结果（同时包含成功和失败信息）
    with open(output, "w") as f:
        json.dump({
            "success_count": len(success_results),
            "failed_count": len(failed_results),
            "total_count": total,
            "results": all_results,
            "zip_path": zip_output_path
        }, f, ensure_ascii=False, indent=2)
    click.echo(Result(code="0", message=output).model_dump_json())


@click.command()
@click.option("--file", required=True, type=str, help="图片文件路径或图片URL地址，多个URL用逗号分隔")
@click.option("--output", required=True, type=str, help="输出结果所在的json文件路径")
def main(file, output):
    """AI美颜SKILL工具，对图片进行美颜处理
    
    支持的输入格式：
    - 单张本地图片路径
    - 单张图片URL
    - 多张图片URL（用逗号分隔）
    - zip/tar/tar.gz/tar.bz2压缩包路径（包含多张图片）
    """
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    # 判断是否为压缩包
    is_archive = file.lower().endswith(('.zip', '.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2', '.tar.xz', '.txz'))
    
    # 判断是否为多个URL（用逗号分隔）
    is_multiple_urls = ',' in file and ('http://' in file or 'https://' in file)
    
    if is_archive:
        # 压缩包 - 直接传给脚本自动处理
        click.echo(f"检测到压缩包({file})，自动解压并处理所有图片...")
        process_archive_file(file, output)
    elif is_multiple_urls:
        # 多张图片URL - 依次处理并打包为zip
        url_list = [url.strip() for url in file.split(',') if url.strip()]
        click.echo(f"检测到 {len(url_list)} 张图片URL，将依次处理并打包为zip...")
        process_multiple_urls(url_list, output)
    else:
        # 单张图片/URL
        result = process_single_image(file)
        with open(output, "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        click.echo(Result(code="0", message=output).model_dump_json())
        click.echo(f"任务完成，结果已保存到 {output}")

if __name__ == "__main__":
    main()
