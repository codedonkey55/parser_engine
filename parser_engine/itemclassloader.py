# find and load scrapy item classes that user defined

import six
import traceback
import warnings
import importlib
from scrapy.utils.misc import walk_modules
from scrapy import Item
import inspect
from collections import defaultdict
from .singleton import Singleton
from .utils import load_scrapy_settings


def iter_item_classes(module):
    """Return an iterator over all spider classes defined in the given module
    that can be instantiated (ie. which have name)
    """
    # this needs to be imported here until get rid of the spider manager
    # singleton in scrapy.spider.spiders
    for obj in six.itervalues(vars(module)):
        if inspect.isclass(obj) and issubclass(obj, Item) and obj.__module__ == module.__name__:
            yield obj


@Singleton
class ItemClassLoader(object):
    """
    # from scrapy import spiderloader
    scrapy的item默认是全部写在一个`items.py`中的，但为了某种拆分的可能性，
    参考了spiderloader的实现
    # from scrapy.loader import ItemLoader
    并且，显然 ItemClassLoader 与 ItemLoader 很不一样
    """

    def __init__(self, lazy_load=False, settings=None):
        self.settings = settings if settings else load_scrapy_settings()
        self.__init(self.settings)
        if not lazy_load:
            self._load_all_items(self.settings.get('BOT_NAME') + ".items")

    def __init(self, settings):
        self._found = defaultdict(list)
        self._items = {}
        self.item_modules = settings.get('ITEM_MODULES', [])
        self._loaded = False

    def _load_items(self, module):
        for spcls in iter_item_classes(module):
            self._found[spcls.__name__].append((module.__name__, spcls.__name__))
            self._items[spcls.__name__] = spcls

    def _load_all_items(self, item_modules=None):
        if item_modules:
            self.item_modules.append(item_modules)
        for name in self.item_modules:
            try:
                for module in walk_modules(name):
                    self._load_items(module)
            except ImportError as e:
                if self.warn_only:
                    msg = ("\n{tb}Could not load spiders from module '{modname}'. "
                           "See above traceback for details.".format(modname=name, tb=traceback.format_exc()))
                    warnings.warn(msg, RuntimeWarning)
                else:
                    raise
        self._loaded = True

    def list(self):
        """
        Return a list with the names of all items available in the project.
        """
        if not self._loaded:
            self._load_all_items()
        return list(self._items.keys())

    def get(self, name):
        if not name:
            return
        if not self._loaded:
            self._load_all_items()
        return self._items.get(name)

    def load(self, name):
        """
        support import-on-call，like:
            cls = ItemClassloader().load('parser_engine.clue.items.ClueItem')
        :param name: absolute import path
        :return: `class` obj
        """
        try:
            cls = self.get(name)
            if not cls and name:
                module, cls_name = name.rsplit('.', 1)
                md = importlib.import_module(module)
                cls = getattr(md, cls_name)
                if cls and inspect.isclass(cls):
                    self._items[name] = cls
            return cls
        except (ImportError, ModuleNotFoundError, Exception):
            warnings.warn("class %s not found" % name, RuntimeWarning)
