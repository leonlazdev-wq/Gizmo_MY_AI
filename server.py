# patched server.py
# -----------------
# BEFORE replacing server.py: run:
#   cp server.py server.py.bak
#
# This wrapper:
# 1) ensures gradio==3.41.2 is installed (best-effort)
# 2) monkeypatches theme classes' set(...) so unexpected kwargs are ignored
# 3) executes the original server.py from server.py.bak
#
# If the backup (server.py.bak) is missing the wrapper exits with instructions.

import os
import sys
import subprocess
import importlib
import inspect
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
BACKUP = os.path.join(HERE, "server.py.bak")

def exit_with(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)

def pip_install(packages):
    try:
        cmd = [sys.executable, "-m", "pip", "install", "--quiet"] + (packages if isinstance(packages, list) else [packages])
        print("Running:", " ".join(cmd))
        subprocess.check_call(cmd)
        return True
    except Exception as e:
        print("pip install failed:", e)
        return False

def ensure_gradio_pinned():
    """Ensure gradio 3.41.2 is installed (best-effort)."""
    try:
        import gradio as gr
        ver = getattr(gr, "__version__", None)
        print("Found gradio version:", ver)
        if not ver or not ver.startswith("3.41"):
            print("Attempting to pin gradio to 3.41.2")
            try:
                subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "gradio", "gradio_client"], check=False)
            except Exception:
                pass
            success = pip_install(["gradio==3.41.2", "gradio_client==0.5.0"])
            if success:
                # attempt to reload gradio
                try:
                    if "gradio" in sys.modules:
                        del sys.modules["gradio"]
                    import importlib
                    gr2 = importlib.import_module("gradio")
                    print("Reloaded gradio version:", getattr(gr2, "__version__", None))
                except Exception as e:
                    print("Warning: reloading gradio failed:", e)
            else:
                print("Warning: pip install gradio failed (continuing, may error later)")
    except Exception:
        # not installed
        print("gradio not importable, attempting to install pinned version")
        pip_install(["gradio==3.41.2", "gradio_client==0.5.0"])

def wrap_method_allow_extra_kwargs(orig):
    """Return wrapper that calls orig and, if TypeError about unexpected kwargs occurs,
       filters kwargs to signature-allowed keys and retries."""
    def new(self, *args, **kwargs):
        try:
            return orig(self, *args, **kwargs)
        except TypeError as e:
            # If TypeError mentions unexpected keyword, try to filter kwargs to allowed ones
            try:
                sig = inspect.signature(orig)
                allowed = {k: v for k, v in kwargs.items() if k in sig.parameters}
                return orig(self, *args, **allowed)
            except Exception:
                # re-raise original
                raise
    return new

def aggressive_monkeypatch_theme_set():
    """
    Aggressively search the gradio package for classes with a `set` method and wrap them
    with a tolerant wrapper so unexpected theme kwargs are ignored instead of raising.
    """
    try:
        import gradio
    except Exception as e:
        print("Could not import gradio for monkeypatching:", e)
        return

    patched = []
    try:
        # Walk gradio package attributes and submodules
        for attr_name in dir(gradio):
            try:
                attr = getattr(gradio, attr_name)
            except Exception:
                continue
            # If module, try to import its attributes
            if hasattr(attr, "__dict__"):
                submod = attr
                # iterate class-like attributes inside
                for k, v in list(submod.__dict__.items()):
                    try:
                        if inspect.isclass(v) and hasattr(v, "set") and callable(getattr(v, "set", None)):
                            orig = getattr(v, "set")
                            # avoid double-wrapping
                            if getattr(orig, "__wrapped_by_tolerant__", False):
                                continue
                            wrapped = wrap_method_allow_extra_kwargs(orig)
                            wrapped.__wrapped_by_tolerant__ = True
                            try:
                                setattr(v, "set", wrapped)
                                patched.append(f"{submod.__name__}.{k}")
                            except Exception as e:
                                # fallback: try set on the function object
                                pass
                    except Exception:
                        continue
        # Also attempt common theme module names
        candidate_modules = [
            "gradio.themes",
            "gradio.themes.base",
            "gradio.themes.default",
            "gradio.themes.material",
            "gradio.themes.base_theme",
        ]
        for modname in candidate_modules:
            try:
                m = importlib.import_module(modname)
                for k, v in list(m.__dict__.items()):
                    if inspect.isclass(v) and hasattr(v, "set") and callable(getattr(v, "set")):
                        orig = getattr(v, "set")
                        if getattr(orig, "__wrapped_by_tolerant__", False):
                            continue
                        wrapped = wrap_method_allow_extra_kwargs(orig)
                        wrapped.__wrapped_by_tolerant__ = True
                        setattr(v, "set", wrapped)
                        patched.append(f"{modname}.{k}")
            except Exception:
                continue
    except Exception as e:
        print("Unexpected error while attempting to monkeypatch gradio theme classes:", e)

    if patched:
        print("Patched theme.set on:", patched)
    else:
        print("No theme classes patched (maybe already compatible or different gradio internals).")

def execute_backup_server():
    """Execute the backed-up original server script in its own globals."""
    if not os.path.exists(BACKUP):
        print("Backup server.py not found:", BACKUP)
        print("Make sure you created a backup before replacing. Command:")
        print("  cp server.py server.py.bak")
        sys.exit(1)

    print("Executing original server from backup:", BACKUP)
    with open(BACKUP, "r", encoding="utf-8") as f:
        src = f.read()
    server_globals = {
        "__name__": "__main__",
        "__file__": BACKUP,
        "__package__": None,
    }
    try:
        exec(compile(src, BACKUP, "exec"), server_globals)
    except SystemExit:
        raise
    except Exception:
        print("Original server crashed after compatibility patches. Traceback:")
        traceback.print_exc()
        sys.exit(1)

def main():
    # 1) Ensure backup exists (the wrapper requires it)
    if not os.path.exists(BACKUP):
        exit_with("ERROR: server.py.bak not found. BACKUP the original server.py first:\n  cp server.py server.py.bak")

    # 2) Pin gradio (best-effort)
    ensure_gradio_pinned()

    # 3) Monkeypatch theme.set aggressively
    aggressive_monkeypatch_theme_set()

    # 4) Execute the original server code (from backup)
    execute_backup_server()

if __name__ == "__main__":
    main()
