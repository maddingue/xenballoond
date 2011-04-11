import imp, re, sys, unittest

sys.path += ["lib"]
modules = [
    "xenballoond.cmdline",
    "xenballoond.meta",
    "xenballoond.xenballoon",
]

# see if pyflakes is available
have_pyflakes = 0
try:
    from pyflakes.scripts.pyflakes import checkPath
    have_pyflakes = 1
except:
    pass


class CheckLoad(unittest.TestCase):
    def test_load(self):
        for module in modules:
            loaded = 0

            # try to compile the module
            try:
                __import__(module)
                loaded = 1
            except:
                pass

            self.assertTrue(loaded, "loading %s" % module)

            # check the module with pyflakes, if available
            if loaded and have_pyflakes:
                path = re.sub('c$', '', sys.modules[module].__file__)
                has_flakes = checkPath(path)
                self.assertTrue(not has_flakes,
                    "checking %s with pyflakes" % module)


if __name__ == "__main__":
    unittest.main()

