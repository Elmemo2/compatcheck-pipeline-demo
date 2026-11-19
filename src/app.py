from utils import normalize_path


def build_log_path(base: str) -> str:
    return normalize_path(base) + "/compatcheck.log"
