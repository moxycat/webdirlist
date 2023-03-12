from flask import *
from pathlib import Path
from sys import argv
import magic
from base64 import b64encode
import re

MB = 1 << 20
BUFSIZE = 10 * MB

BASE_PATH = Path.cwd()

app = Flask(__name__)

def get_range(request):
    range = request.headers.get('Range')
    m = re.match(r"bytes=(?P<start>\d+)-(?P<end>\d+)?", range)
    if m:
        start = int(m.group("start"))
        end = m.group("end")
        if end is not None: end = int(end)
        return start, end
    else: return 0, None

def partial_response(path: Path, start, end=None):
    size = path.stat().st_size
    if end is None:
        end = start + BUFSIZE - 1
    end = min(min(end, size - 1), start + BUFSIZE - 1)
    length = end - start + 1
    with path.open("rb") as f:
        f.seek(start)
        data = f.read(length)
    assert len(data) == length
    resp = Response(data, 206, mimetype=magic.from_file(str(path.absolute()), mime=True), direct_passthrough=True)
    resp.headers.add("Content-Range", "bytes %d-%d/%d" % (start, end, size))
    resp.headers.add("Accept-Ranges", "bytes")
    return resp

@app.route("/static/<path:path>")
def static_(path):
    send_from_directory(Path.cwd() / "static", path)

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    relpath = Path(path)
    p = BASE_PATH.joinpath(relpath)
    m = request.args.get("m")
    if m is not None:
        start, end = get_range(request)
        return partial_response(p, start, end)

    if not p.exists():
        return "This file is not present on the server."
    if p.is_dir():
        ents = [(e.relative_to(BASE_PATH), e.is_file(), e.is_dir()) for e in p.glob("*")]
        ents.sort(key=lambda t: (BASE_PATH / t[0]).stat().st_ctime)
        ents.sort(key=lambda t: t[1])
        total_files = sum(1 for e in ents if e[1])
        total_dirs = sum(1 for e in ents if e[2])
        return render_template("list.html", entries=ents, path=("/" / relpath).as_posix(), files=total_files, dirs=total_dirs)
    elif p.is_file():
        mime = magic.from_file(str(p.absolute()), mime=True)
        print(mime)
        match mime.split("/")[0]:
            case "text": return render_template("text.html", path=p)
            case "image":
                data = b64encode(p.read_bytes()).decode()
                return render_template("image.html", path=p.relative_to(BASE_PATH).as_posix(), mime=mime, data=data)
            case "video":
                loc = "%s?m=v" % ("/" / p.relative_to(BASE_PATH)).as_posix()
                print(loc)
                return render_template("video.html", path=p, video=loc)
            case _:
                return send_from_directory(p.parent, p.name)
        

if __name__ == "__main__":
    if len(argv) > 1: BASE_PATH = Path(argv[1])
    app.run(host="0.0.0.0", port=80)
    #app.run(debug=True)