"""Browser and driver installer classes."""

from browserget.installers.base import AbstractBrowserInstaller, AbstractDriverInstaller
from browserget.installers.chrome import ChromeInstaller
from browserget.installers.chromedriver import ChromeDriverInstaller
from browserget.installers.edge import EdgeDriverInstaller, EdgeInstaller
from browserget.installers.firefox import FirefoxInstaller
from browserget.installers.geckodriver import GeckoDriverInstaller

__all__ = [
    "AbstractBrowserInstaller",
    "AbstractDriverInstaller",
    "ChromeDriverInstaller",
    "ChromeInstaller",
    "EdgeDriverInstaller",
    "EdgeInstaller",
    "FirefoxInstaller",
    "GeckoDriverInstaller",
]
