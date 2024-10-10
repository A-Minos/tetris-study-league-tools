import signal
from asyncio import Task, create_task, gather
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from hashlib import md5
from io import BytesIO
from multiprocessing import Manager, Queue
from typing import Any

import xlsxwriter
from nicegui import app, ui
from nicegui.events import ValueChangeEventArguments
from yarl import URL

from .api.player import Player
from .api.schemas.user import User
from .api.typing import Rank
from .avatar import generate_identicon
from .constant import USER_ID, USER_NAME
from .exception import RequestError
from .log import logger
from .request import Request
from .retry import retry

inputs = ''

req = Request(None)

task: list[Task] = []


def handler(signum, frame) -> None:  # noqa: ANN001, ARG001
    logger.info('stop')
    app.stop()


signal.signal(signal.SIGINT, handler)
signal.signal(signal.SIGTERM, handler)


@dataclass
class UserInfo:
    id: int
    user: User
    rank: Rank
    tr: float
    sprint: str
    avatar: bytes


BASE_URL = URL('https://tetr.io/user-content/')


class Collect[**P, T]:
    def __init__(self, func: Callable[P, Coroutine[Any, Any, T]]) -> None:
        self.func = func
        self.result: list[T] = []

    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        result = await self.func(*args, **kwargs)
        self.result.append(result)
        return result

    def clear(self) -> None:
        self.result.clear()


async def get_avatar(user: User, revision: int) -> bytes:
    return await req(BASE_URL / 'avatars' / f'{user.ID}.jpg' % {'rv': revision}, is_json=False)


@Collect
@retry(exception_type=RequestError)
async def get_user_info(id: int, user_id_or_name: str) -> UserInfo:
    if USER_ID.match(user_id_or_name):
        player = Player(user_id=user_id_or_name, trust=True)
    elif USER_NAME.match(user_id_or_name):
        player = Player(user_name=user_id_or_name, trust=True)
    else:
        msg = f'{user_id_or_name} 不是一个有效的用户名/ID'
        raise ValueError(msg)
    user, league, sprint, avatar_revision = await gather(
        player.user, player.league, player.sprint, player.avatar_revision
    )
    return UserInfo(
        id=id + 1,
        user=user,
        rank=league.data.rank,
        tr=league.data.tr,
        sprint=(
            f'{duration:.3f}s'
            if (duration := timedelta(milliseconds=sprint.data.record.results.stats.finaltime).total_seconds()) < 60  # noqa: PLR2004
            else f'{duration // 60:.0f}m {duration % 60:.3f}s'
        )
        if sprint.data.record is not None
        else 'N/A',
        avatar=await get_avatar(user, avatar_revision)
        if avatar_revision is not None
        else await generate_identicon(md5(user.ID.encode()).hexdigest()),  # noqa: S324
    )


def update_table(task: Task[UserInfo], table: ui.table, queue: Queue) -> None:
    result = task.result()
    table.add_rows(
        {
            'sn': result.id,
            'user': result.user.name.upper(),
            'rank': result.rank.upper(),
            'tr': result.tr,
            'sprint': result.sprint,
        }
    )
    queue.put(f'{result.user.name.upper()} 获取完成')


async def update_result(table: ui.table, queue: Queue) -> None:
    tasks = []
    callback = partial(update_table, table=table, queue=queue)
    for i, v in enumerate(inputs.splitlines()):
        task = create_task(get_user_info(i, v))
        task.add_done_callback(callback)
        tasks.append(task)
    if tasks:
        await gather(*tasks)
    queue.put('完成')


def validate_users(result: ui.markdown, event: ValueChangeEventArguments) -> None:
    for i, v in enumerate(event.value.splitlines()):
        if USER_ID.match(v):
            continue
        if USER_NAME.match(v):
            continue
        result.set_content(f'<font color=#ff7100>第 **{i+1}** 行 `{v}` 是无效的 TETR.IO 用户名/ID</font>')
        return
    if event.value == '':
        result.set_content('')
    else:
        result.set_content('<font color=#42e73a>验证通过</font>')


def to_excel(data: list[UserInfo]) -> bytes:
    io = BytesIO()
    workbook = xlsxwriter.Workbook(io, {'in_memory': True})
    worksheet = workbook.add_worksheet()
    worksheet.write('A1', '序号')
    worksheet.write('B1', '用户名')
    worksheet.write('C1', '段位')
    worksheet.write('D1', 'TR')
    worksheet.write('E1', '40L')
    for i, v in enumerate(data):
        worksheet.write(f'A{i+2}', v.id)
        worksheet.write(f'B{i+2}', v.user.name.upper())
        worksheet.write(f'C{i+2}', v.rank)
        worksheet.write(f'D{i+2}', v.tr)
        worksheet.write(f'E{i+2}', v.sprint)
    workbook.close()
    return io.getvalue()


@ui.page('/')
async def page() -> None:
    ui.label('TSL-Tools').style('font-size: 24px; font-weight: bold; text-align: center; margin-top: 20px;')
    users = ui.textarea('用户名 每行一个').classes('w-full').bind_value(globals(), 'inputs')
    feedback = ui.markdown()
    users.on_value_change(partial(validate_users, feedback))
    ui.button('提交', on_click=lambda: ui.open('/result'))


@ui.page('/result')
async def result() -> None:
    columns = [
        {'name': 'sn', 'label': '序号', 'field': 'sn', 'required': True, 'sortable': True},
        {'name': 'user', 'label': '用户名', 'field': 'user', 'required': True, 'align': 'left'},
        {'name': 'rank', 'label': '段位', 'field': 'rank', 'required': True, 'sortable': True},
        {'name': 'tr', 'label': 'TR', 'field': 'tr', 'required': True, 'sortable': True},
        {'name': 'sprint', 'label': '40L', 'field': 'sprint', 'required': True, 'sortable': True},
    ]
    table = ui.table(columns=columns, rows=[], row_key='name')
    queue = Manager().Queue()

    def timer_callback() -> None:
        if queue.empty():
            return
        if (data := queue.get()) == '完成':
            timer.deactivate()
            spinner.delete()
            with ui.row():
                ui.button('返回', on_click=lambda: ui.open('/') or get_user_info.clear())
                if table.rows:
                    ui.button('下载表格', on_click=lambda: ui.download(to_excel(get_user_info.result), 'test.xlsx'))
                    ui.button(
                        '下载头像',
                        on_click=lambda: [
                            ui.download(i.avatar, f'{i.user.name.upper()}.jpg') for i in get_user_info.result
                        ],
                    )
        ui.notify(data)

    timer = ui.timer(0.1, callback=timer_callback)
    spinner = ui.spinner(size='lg')
    task.append(create_task(update_result(table, queue)))


ui.run(port=5555, show=False, dark=True, language='zh-CN', reload=False)
