import logging
from os_ken import cfg
from os_ken.topology import switches
from os_ken.base.app_manager import AppManager

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s %(name)s: %(message)s'
)

cfg.CONF.set_override('observe_links', True)

AppManager.run_apps(['sp_controller', 'ai_bridge'])
