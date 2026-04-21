import sys
import click
import logging
import jsonpath

from base import Result, authentication, perror

__all__ = ["do_request"]

service, module = authentication(), ""
if 0 == service:
    perror(Result(code="10010", message="AK/SK未配置"))
if 1 == service:
    import servicev1

    do_request = servicev1._do_request
if 2 == service:
    import servicev2

    do_request = servicev2._do_request


# 查询&注册免费的Ark Claw 套餐
@click.command()
def combo() -> None:
    """查询&注册免费的Ark Claw 套餐"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")
    try:
        resp = do_request("POST", {}, b"", action="RegisterArkClawCombo").json()
        # >>> [火山OpenTop错误] >>> #
        open_top_code = jsonpath.jsonpath(resp, "$.ResponseMetadata.Error.CodeN")
        if open_top_code and open_top_code[0] != 0:
            click.echo(Result(code=str(open_top_code), message=""), err=True)
            exit(1)

        # >>> [创作云错误] >>> #
        code = jsonpath.jsonpath(resp, "$.ResponseMetadata.Code")
        if code and code[0] != 0:
            click.echo(Result(code=str(code), message=""), err=True)
            exit(1)

        # >>> [创作云成功] >>> #
        if code and code[0] == 0:
            result = jsonpath.jsonpath(resp, "$.Result")
            if not result or not result[0]:
                click.echo(Result(code="-1", message="接口返回值解析错误"), err=True)
                exit(1)
            expire = jsonpath.jsonpath(resp, "$.Result.expire_time")
            click.echo(Result(code="0", message=str(expire and expire[0])))
            exit(0)

        click.echo(Result(code="-1", message="接口返回值解析错误"), err=True)
    except Exception as e:
        click.echo(Result(code="-1", message=str(e)), err=True)


if __name__ == "__main__":
    combo()
