from asyncio import gather
from hashlib import sha1
from pathlib import Path
from typing import Optional, Set, Union, cast

from pynvim import Nvim
from std2.types import Void, VoidType, or_else

from .cartographer import new, update
from .consts import SESSION_DIR
from .da import dump_json, load_json
from .git import status
from .nvim import getcwd
from .quickfix import quickfix
from .render import render
from .types import (
    FilterPattern,
    Index,
    Mode,
    Node,
    QuickFix,
    Selection,
    Session,
    Settings,
    State,
    VCStatus,
)


def session_path(cwd: str) -> Path:
    hashed = sha1(cwd.encode()).hexdigest()
    part = SESSION_DIR / hashed
    return part.with_suffix("json")


def load_session(cwd: str) -> Session:
    load_path = session_path(cwd)
    json = load_json(load_path)
    nil_session = Session(index={cwd}, show_hidden=False)
    if json:
        try:
            session = Session(
                index={*json.get("index", (cwd,))},
                show_hidden=json.get("show_hidden", False),
            )
        except Exception:
            return nil_session
        else:
            return session
    else:
        return nil_session


def dump_session(state: State) -> None:
    load_path = session_path(state.root.path)
    json = {"index": [*state.index], "show_hidden": state.show_hidden}
    dump_json(load_path, json)


async def initial(nvim: Nvim, settings: Settings) -> State:
    version_ctl = settings.version_ctl
    cwd = await getcwd(nvim)

    session = load_session(cwd)
    index = session.index if settings.session else {cwd}
    show_hidden = session.show_hidden if settings.session else settings.show_hidden

    selection: Selection = set()
    node, qf = await gather(new(cwd, index=index), quickfix(nvim))
    vc = VCStatus() if not version_ctl.enable or version_ctl.defer else await status()

    current = None
    filter_pattern = None

    derived = render(
        node,
        settings=settings,
        index=index,
        selection=selection,
        filter_pattern=filter_pattern,
        qf=qf,
        vc=vc,
        show_hidden=show_hidden,
        current=current,
    )

    state = State(
        index=index,
        selection=selection,
        filter_pattern=filter_pattern,
        show_hidden=show_hidden,
        follow=settings.follow,
        enable_vc=settings.version_ctl.enable,
        width=settings.width,
        root=node,
        qf=qf,
        vc=vc,
        current=current,
        derived=derived,
    )
    return state


async def forward(
    state: State,
    *,
    settings: Settings,
    root: Union[Node, VoidType] = Void,
    index: Union[Index, VoidType] = Void,
    selection: Union[Selection, VoidType] = Void,
    filter_pattern: Union[Optional[FilterPattern], VoidType] = Void,
    show_hidden: Union[bool, VoidType] = Void,
    follow: Union[bool, VoidType] = Void,
    enable_vc: Union[bool, VoidType] = Void,
    width: Union[int, VoidType] = Void,
    qf: Union[QuickFix, VoidType] = Void,
    vc: Union[VCStatus, VoidType] = Void,
    current: Union[str, VoidType] = Void,
    paths: Union[Set[str], VoidType] = Void,
) -> State:
    new_index = or_else(index, state.index)
    new_selection = or_else(selection, state.selection)
    new_filter_pattern = or_else(filter_pattern, state.filter_pattern)
    new_current = or_else(current, state.current)
    new_root = cast(
        Node,
        root
        or (
            await update(state.root, index=new_index, paths=cast(Set[str], paths))
            if paths
            else state.root
        ),
    )
    new_qf = or_else(qf, state.qf)
    new_vc = or_else(vc, state.vc)
    new_hidden = or_else(show_hidden, state.show_hidden)
    lookup, rendered = render(
        new_root,
        settings=settings,
        index=new_index,
        selection=new_selection,
        filter_pattern=new_filter_pattern,
        qf=new_qf,
        vc=new_vc,
        show_hidden=new_hidden,
        current=new_current,
    )
    paths_lookup = {node.path: idx for idx, node in enumerate(lookup)}

    new_state = State(
        index=new_index,
        selection=new_selection,
        filter_pattern=new_filter_pattern,
        show_hidden=new_hidden,
        follow=or_else(follow, state.follow),
        enable_vc=or_else(enable_vc, state.enable_vc),
        width=or_else(width, state.width),
        root=new_root,
        qf=new_qf,
        vc=new_vc,
        current=new_current,
        lookup=lookup,
        paths_lookup=paths_lookup,
        rendered=rendered,
    )

    return new_state


def index(state: State, row: int) -> Optional[Node]:
    if (row > 0) and (row < len(state.lookup)):
        return state.lookup[row]
    else:
        return None


def is_dir(node: Node) -> bool:
    return Mode.folder in node.mode
