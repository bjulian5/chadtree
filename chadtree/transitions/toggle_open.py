from argparse import ArgumentParser
from typing import NoReturn, Optional, Sequence

from pynvim import Nvim
from pynvim_pp.lib import s_write

from ..registry import rpc
from ..settings.types import Settings
from ..state.types import State
from .shared.current import current
from .shared.wm import find_current_buffer_name, toggle_fm_window
from .types import OpenArgs, Stage


class _ArgparseError(Exception):
    pass


class _Argparse(ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _ArgparseError(message)

    def exit(self, status: int = 0, message: Optional[str] = None) -> NoReturn:
        msg = self.format_help()
        raise _ArgparseError(msg)


def _parse_args(args: Sequence[str]) -> OpenArgs:
    parser = _Argparse()
    parser.add_argument("--nofocus", dest="focus", action="store_false", default=True)

    ns = parser.parse_args(args=args)
    opts = OpenArgs(focus=ns.focus)
    return opts


@rpc(blocking=False)
def _open(
    nvim: Nvim, state: State, settings: Settings, args: Sequence[str]
) -> Optional[Stage]:
    """
    Toggle sidebar
    """

    try:
        opts = _parse_args(args)
    except _ArgparseError as e:
        s_write(nvim, e, error=True)
        return None
    else:
        curr = find_current_buffer_name(nvim)
        toggle_fm_window(nvim, state=state, settings=settings, opts=opts)

        stage = current(nvim, state=state, settings=settings, current=curr)
        if stage:
            return stage
        else:
            return Stage(state)
