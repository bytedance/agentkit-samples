# Copyright 2026 ByteDance
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


import click
from core import Result
from core.api.iccp.service import IccpService


# 查询&注册免费的Ark Claw 套餐
@click.command()
def main() -> None:
    """查询&注册免费的Ark Claw 套餐"""
    try:
        iccp_service = IccpService()
        resp = iccp_service.post("RegisterArkClawCombo", b"")
        click.echo(resp)
    except Exception as e:
        click.echo(Result(code="-1", message=str(e)), err=True)


if __name__ == "__main__":
    main()
