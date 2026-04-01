# audit_helper_poc/logger.py
import logging


class Logger:
    """日志管理器"""

    LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }

    def __init__(self, name: str = "audit_helper_poc", level: str = "INFO"):
        """
        初始化日志器。

        Args:
            name: 日志器名称
            level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        """
        self.name = name
        self.level = level
        self._logger = logging.getLogger(name)
        self._logger.setLevel(self.LEVELS.get(level, logging.INFO))

        # 如果没有 handler，添加一个
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(self.LEVELS.get(level, logging.INFO))
            formatter = logging.Formatter('[%(levelname)s] %(message)s')
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

    def debug(self, message: str) -> None:
        """输出 DEBUG 级别日志"""
        self._logger.debug(message)

    def info(self, message: str) -> None:
        """输出 INFO 级别日志"""
        self._logger.info(message)

    def warning(self, message: str) -> None:
        """输出 WARNING 级别日志"""
        self._logger.warning(message)

    def error(self, message: str) -> None:
        """输出 ERROR 级别日志"""
        self._logger.error(message)