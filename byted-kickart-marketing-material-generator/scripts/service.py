import sys
import jsonpath

import logging
from model import *

def perror(res: Result):
    if res.code != "0": print(res.model_dump_json())
    exit(1)

service, module = authentication(), ""
if 0 == service:
    perror(Result(code='10010', message="AK/SK未配置"))
if 1 == service:
    import servicev1
    do_request = servicev1._do_request
if 2 == service:
    import servicev2
    do_request = servicev2._do_request

# 查询&注册免费的Ark Claw 套餐
def combo()->Result:
        try:
            resp = do_request("POST", {}, b'', action="RegisterArkClawCombo").json()
            # >>> [火山OpenTop错误] >>> #
            open_top_code = jsonpath.jsonpath(resp, "$.ResponseMetadata.Error.CodeN")
            if open_top_code and open_top_code[0] != 0:
                return Result(code=str(open_top_code), message="")

            # >>> [创作云错误] >>> #
            code = jsonpath.jsonpath(resp, "$.ResponseMetadata.Code")
            if code and code[0] != 0:
                return Result(code=str(code), message="")

            # >>> [创作云成功] >>> #
            if code and code[0] == 0:
                result = jsonpath.jsonpath(resp, "$.Result")
                if not result or not result[0]: 
                    return Result(code="-1", message="接口返回值解析错误")
                expire = jsonpath.jsonpath(resp, "$.Result.expire_time")
                return Result(code='0', message=str(expire and expire[0]))

            return Result(code="-1", message="接口返回值解析错误")
        except Exception as e:
            return Result(code="-1", message=str(e))

if __name__ == "__main__":
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")
    print(combo().model_dump_json())