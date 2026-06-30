import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
import pathlib

DATA_DIR = pathlib.Path("/home/marc/monitoring/data")

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode()

        current = DATA_DIR / "weather.csv"
        last_day = DATA_DIR / "weather_last-day.csv"
        last_week = DATA_DIR / "weather_last-week.csv"
        filenames = [last_day, last_week]
        maxlines = [60 * 24, 60 * 24 * 7]

        DATA_DIR.mkdir(exist_ok=True)

        if not last_day.exists():
            with open(last_day, "a") as f:
                f.write("date,time,temp,hum,press,co2\n")
        if not last_week.exists():
            with open(last_week, "a") as f:
                f.write("date,time,temp,hum,press,co2\n")

        with open(current, "w") as f:
            f.write("date,time,temp,hum,press,co2\n")
            f.write(post_data + "\n")
        for filename in filenames:
            with open(filename, "a") as f:
                f.write(post_data + "\n")

        for filename, maxl in zip(filenames, maxlines):
            with open(filename, "r") as f:
                data = f.readlines()
            if len(data) > maxl + 1:
                header, last_lines = data[0], data[-maxl:]
                with open(filename, "w") as f:
                    f.writelines([header] + last_lines)

        self.send_response(200)
        self.end_headers()

server = HTTPServer(("0.0.0.0", 8000), Handler)
print("Server running on port 8000...", file=sys.stderr)
server.serve_forever()

