"""Medidas da interface em pixels, acompanhando a escala de fonte do Tk."""

import sys


def enable_dpi_awareness():
    """Evita a ampliação de um bitmap pelo Windows; deve preceder o Tk().

    O Tk 8.6 usa a escala do monitor do sistema. Não anunciamos suporte a
    mudança de DPI entre monitores, que exigiria redimensionar cada widget.
    O executável usa a mesma configuração no manifesto do Windows.
    """
    if sys.platform != "win32":
        return
    import ctypes

    try:
        # SYSTEM_AWARE: -2. Um manifesto já ativo pode impedir a chamada.
        setter = ctypes.windll.user32.SetProcessDpiAwarenessContext
        setter.argtypes = [ctypes.c_void_p]
        setter.restype = ctypes.c_bool
        if setter(ctypes.c_void_p(-2)):
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


class DisplayMetrics:
    """O desenho usa medidas a 96 DPI; fontes continuam em pontos do Tk."""

    def __init__(self, root):
        self.root = root
        self.scale = max(0.5, min(4.0, root.winfo_fpixels("1i") / 96.0))

    def px(self, value):
        if isinstance(value, (tuple, list)):
            return tuple(self.px(part) for part in value)
        return round(value * self.scale)

    def configure_window(self):
        # Reserva espaço para a barra de tarefas, decoração e bordas. A
        # resolução é a que o processo enxerga após declarar seu DPI.
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        available_w = max(1, screen_w - self.px(48))
        available_h = max(1, screen_h - self.px(96))
        width, height = min(self.px(1220), available_w), min(self.px(800), available_h)
        self.root.minsize(min(self.px(920), available_w), min(self.px(640), available_h))
        self.root.geometry(f"{width}x{height}+{max(0, (screen_w - width) // 2)}+{self.px(24)}")
