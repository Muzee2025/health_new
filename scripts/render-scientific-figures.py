#!/usr/bin/env python3
"""Export synthetic chart-library fixtures; Python >=3.9, matplotlib, numpy, Pillow.

No API, database, student records, network, package installation or LaTeX is used.
Run from any directory. Each invocation creates a new directory under --output.
"""
from __future__ import annotations  # noqa: I001

import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone
import warnings
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "docs/design/chart-demo-data.js"
PALETTE = ROOT / "docs/design/chart-palette.json"
SCHEMA = "xinyu-scientific-fixture-v1"


def digest(content):
    return hashlib.sha256(content).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_fixtures(node):
    executable = shutil.which(node)
    if not executable:
        raise ValueError("Node.js is required to import the existing chart-demo-data.js generator.")
    code = """import {getChartDemoData} from './docs/design/chart-demo-data.js';
const fixtures = [7,14,30].flatMap(range => ['A','B'].map(sample => getChartDemoData({range,sample})));
process.stdout.write(JSON.stringify(fixtures));"""
    result = subprocess.run([executable, "--input-type=module", "-e", code], cwd=ROOT,
                            capture_output=True, encoding="utf-8", check=True, timeout=30)
    return json.loads(result.stdout), subprocess.run([executable, "--version"], capture_output=True,
                                                    text=True, check=True, timeout=10).stdout.strip()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_data(data):
    """Independently recompute the eight gallery aggregates from raw daily rows."""
    require(data["range"] in (7, 14, 30) and data["sample"] in ("A", "B"), "Invalid fixture range/sample.")
    daily = data["daily"]
    require(len(daily) == data["range"], "Daily-row count differs from selected range.")
    dates = [datetime.strptime(day["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc) for day in daily]
    require(all((b-a).days == 1 for a,b in zip(dates, dates[1:])), "UTC dates are not consecutive.")  # noqa: B905
    require(dates[-1].date().isoformat() == "2026-10-21", "Unexpected synthetic fixture end date.")
    for day, date in zip(daily, dates):  # noqa: B905
        require(day["weekday"] == date.weekday(), "UTC weekday mismatch.")
        require(day["support"] == sum(day["channels"]) == len(day["durations"]), "Support/channel/duration totals differ.")
        require(day["planned"] == sum(day["slots"]) and 0 <= day["completed"] <= day["planned"], "Appointment counts differ.")
    for index, row in enumerate(data["emotions"]):
        require(row["value"] == sum(day["emotions"][index] for day in daily), "Emotion aggregation differs.")
    for index, row in enumerate(data["risks"]):
        require(row["value"] == sum(day["risks"][index] for day in daily), "Risk aggregation differs.")
    require([row["field"] for row in data["risks"]] == ["low", "mid", "high"], "Unexpected risk order.")
    for weekday, row in enumerate(data["appointments"]):
        days = [day for day in daily if day["weekday"] == weekday]
        for field in ("planned", "completed"):
            require(row[field] == sum(day[field] for day in days), "Weekday appointment aggregation differs.")
    for weekend, row in enumerate(data["channels"]):
        days = [day for day in daily if (day["weekday"] >= 5) == bool(weekend)]
        counts = [sum(day["channels"][index] for day in days) for index in range(3)]
        require(row["counts"] == counts and row["total"] == sum(counts), "Channel aggregation differs.")
        # JavaScript Math.round for these nonnegative percentages (Python round uses ties-to-even).
        tenths = [math.floor(value / sum(counts) * 1000 + 0.5) for value in counts[:2]]
        tenths.append(1000 - sum(tenths))
        require(row["percentages"] == [value / 10 for value in tenths], "Channel percentages differ.")
    require(len(data["heatmap"]) == 28, "Heatmap must contain 28 cells.")
    require(len({(row["weekday"],row["time"]) for row in data["heatmap"]}) == 28, "Duplicate heatmap cell.")
    for row in data["heatmap"]:
        require(0 <= row["weekday"] < 7 and 0 <= row["time"] < 4, "Heatmap index out of range.")
        require(row["value"] == sum(day["slots"][row["time"]] for day in daily if day["weekday"] == row["weekday"]), "Heatmap cell differs.")
    heat_total = sum(row["value"] for row in data["heatmap"])
    require(heat_total == sum(day["planned"] for day in daily), "Heatmap/planned total differs.")
    durations = [value for day in daily for value in day["durations"]]
    require(data["durations"] == durations and len(durations) > 0, "Raw duration data differs or is empty.")
    require(all(isinstance(value, (int,float)) and math.isfinite(value) and 0 <= value < 80 for value in durations), "Invalid raw duration.")
    require(len(data["histogram"]) == 8, "Expected eight duration bins.")
    counts = []
    for index,row in enumerate(data["histogram"]):
        require(row["min"] == index*10 and row["max"] == (index+1)*10, "Unexpected duration-bin edges.")
        count = sum(row["min"] <= value < row["max"] for value in durations)
        require(row["value"] == count, "Histogram count differs from raw records.")
        counts.append(count)
    require(sum(counts) == len(durations), "Histogram dropped/double-counted records.")
    for index,row in enumerate(data["resources"]):
        for field in ("views", "saves"):
            require(row[field] == sum(day["resources"][index][field] for day in daily), "Resource aggregation differs.")
        require(0 <= row["saves"] <= row["views"], "Resource saves exceed views.")
    return {"range":data["range"], "sample":data["sample"], "utc_start":daily[0]["date"],
            "utc_end":daily[-1]["date"], "support_count":sum(day["support"] for day in daily),
            "daily_support_min_max":[min(day["support"] for day in daily),max(day["support"] for day in daily)],
            "risk_observation_count":sum(row["value"] for row in data["risks"]),
            "heatmap_total":heat_total, "duration_record_count":len(durations), "histogram_bins":counts,
            "raw_duration_min_max_minutes":[min(durations),max(durations)],
            "raw_duration_mean_minutes":sum(durations)/len(durations), "all_eight_aggregates":"passed"}


def load_palette(path):
    raw = path.read_bytes()
    palette = json.loads(raw)
    from matplotlib.colors import is_color_like
    for key in ("surface", "text", "muted", "grid", "primary", "secondary", "comparison"):
        require(is_color_like(palette["colors"][key]), "Invalid palette color: " + key)
    for key in ("low", "mid", "high"):
        require(is_color_like(palette["risks"][key]), "Invalid palette risk: " + key)
    require(len(palette["sequential"]) >= 2 and all(is_color_like(c) for c in palette["sequential"]), "Invalid sequential palette.")
    return palette, digest(raw)


def configure_style(requested, palette):
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    result = {"requested":requested, "effective":"matplotlib-builtin", "scienceplots":"unavailable", "fallback_reason":None}
    if requested == "science":
        try:
            import scienceplots  # noqa: F401 - registers style files only
            plt.style.use(["science", "no-latex"])
            result.update(effective="science+no-latex", scienceplots=importlib.metadata.version("SciencePlots"))
        except (ImportError, OSError) as error:
            result["fallback_reason"] = type(error).__name__ + ": SciencePlots unavailable; built-in style used."
            print(result["fallback_reason"], file=sys.stderr)
    else:
        try:
            result["scienceplots"] = importlib.metadata.version("SciencePlots")
        except importlib.metadata.PackageNotFoundError:
            pass
    colors = palette["colors"]
    mpl.rcParams.update({"font.family":"DejaVu Sans", "font.size":8, "axes.labelsize":8,
        "axes.titlesize":11, "axes.titleweight":"bold", "xtick.labelsize":8, "ytick.labelsize":8,
        "legend.fontsize":8, "axes.spines.top":False, "axes.spines.right":False,
        "axes.linewidth":0.7, "axes.edgecolor":colors["muted"], "text.color":colors["text"],
        "axes.labelcolor":colors["text"], "xtick.color":colors["muted"], "ytick.color":colors["muted"],
        "figure.facecolor":colors["surface"], "axes.facecolor":colors["surface"],
        "savefig.facecolor":colors["surface"], "axes.grid":False, "text.usetex":False,
        "pdf.fonttype":42, "ps.fonttype":42, "svg.fonttype":"none", "axes.unicode_minus":False,
        "xtick.minor.visible":False, "ytick.minor.visible":False})
    return result


def draw_panel(kind, fig, ax, data, palette, metrics, compact=False):
    import numpy as np  # noqa: I001
    import matplotlib.dates as mdates
    from matplotlib.ticker import MaxNLocator
    from matplotlib.colors import LinearSegmentedColormap, to_rgb
    colors = palette["colors"]
    titles = {"trend":"Daily support activity", "risk":"Risk-level observations",
              "heatmap":"Scheduled appointments by weekday and time", "histogram":"Support-session duration distribution"}
    ax.set_title(titles[kind], loc="left", pad=12)
    if kind == "trend":
        dates = [datetime.strptime(day["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc) for day in data["daily"]]
        values = [day["support"] for day in data["daily"]]
        ax.plot(dates, values, color=colors["primary"], marker="o", markersize=3.5, linewidth=1.5)
        ax.set_ylim(0, max(values)*1.2)
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=5 if compact else 7))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d", tz=timezone.utc))
        ax.set_xlabel("Calendar date (UTC)")
        ax.set_ylabel("Support activity (count)")
        ax.text(0.98,0.95,f"Total = {metrics['support_count']} activities", transform=ax.transAxes, ha="right", va="top", fontsize=8)
    elif kind == "risk":
        labels = ["Low", "Moderate", "High"]
        values = [row["value"] for row in data["risks"]]
        bars = ax.barh(labels, values, color=[palette["risks"][row["field"]] for row in data["risks"]], height=0.55,
                       edgecolor=colors["text"], linewidth=0.5)
        for bar, value, hatch in zip(bars,values,["", "///", "xxx"]):  # noqa: B905
            bar.set_hatch(hatch)
            ax.text(value+max(values)*0.025,bar.get_y()+bar.get_height()/2,str(value),va="center",fontsize=8)
        ax.set_xlim(0,max(values)*1.2)
        ax.invert_yaxis()
        ax.set_xlabel("Risk observations (count)")
        ax.set_ylabel("Risk level (category)")
    elif kind == "heatmap":
        matrix = np.zeros((4,7), dtype=int)
        for row in data["heatmap"]:
            matrix[row["time"],row["weekday"]] = row["value"]
        cmap = LinearSegmentedColormap.from_list("shared-sequential", palette["sequential"])
        maximum = int(matrix.max())
        mesh = ax.pcolormesh(np.arange(8)-0.5,np.arange(5)-0.5,matrix,cmap=cmap,vmin=0,vmax=maximum,
                             edgecolors=colors["surface"], linewidth=1.0, rasterized=False)
        ax.set_xticks(range(7),["Mon","Tue","Wed","Thu","Fri","Sat","Sun"])
        ax.set_yticks(range(4),["09-12","12-15","15-18","18-21"])
        ax.invert_yaxis()
        ax.set_xlabel("Weekday (UTC)")
        ax.set_ylabel("Time slot (hour, UTC)")
        def luminance(color):
            rgb = to_rgb(color)
            return sum(weight*(v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4) for weight,v in zip((0.2126,0.7152,0.0722),rgb))  # noqa: B905
        for time,weekday in np.ndindex(matrix.shape):
            fill_luminance = luminance(cmap(matrix[time,weekday]/maximum if maximum else 0))
            candidate = max((colors["text"],colors["surface"]), key=lambda c:(max(luminance(c),fill_luminance)+0.05)/(min(luminance(c),fill_luminance)+0.05))
            ax.text(weekday,time,str(matrix[time,weekday]),ha="center",va="center",color=candidate,fontsize=8)
        colorbar = fig.colorbar(mesh,ax=ax,pad=0.025,fraction=0.045)
        if colorbar.solids is not None:
            colorbar.solids.set_rasterized(False)
        colorbar.set_label("Scheduled appointments (count)",fontsize=8)
        colorbar.ax.tick_params(labelsize=8)
        colorbar.set_ticks(sorted({round(maximum*step/4) for step in range(5)}))
        for spine in ax.spines.values():
            spine.set_visible(False)
    elif kind == "histogram":
        values = [row["value"] for row in data["histogram"]]
        ax.bar(range(0,80,10),values,width=10,align="edge",color=colors["primary"],edgecolor=colors["surface"],linewidth=0.8)
        ax.axvline(metrics["raw_duration_mean_minutes"],color=colors["comparison"],linestyle="--",linewidth=1.4,
                   label=f"Raw mean = {metrics['raw_duration_mean_minutes']:.2f} min")
        ax.legend(loc="upper left",bbox_to_anchor=(0,1.04),frameon=False,handlelength=2)
        ax.set_xlim(0,80)
        ax.set_ylim(0,max(values)*1.35)
        ax.set_xticks(range(0,81,10))
        ax.set_xlabel("Session duration (min); bins [left, right)")
        ax.set_ylabel("Session records (count)")
    if kind != "heatmap":
        axis = ax.xaxis if kind == "risk" else ax.yaxis
        axis.set_major_locator(MaxNLocator(integer=True,nbins=5))
        ax.set_axisbelow(True)
        ax.grid(axis="x" if kind == "risk" else "y",color=colors["grid"],linewidth=0.5)
    ax.tick_params(length=3,width=0.6)


def add_caption(fig, data, kind, metrics):
    start,end = data["daily"][0]["date"],data["daily"][-1]["date"]
    context = {"trend":f"n = {data['range']} daily counts; {metrics['support_count']} activities.",
               "risk":f"n = {metrics['risk_observation_count']} risk observations; separate denominator from support activity.",
               "heatmap":f"n = {metrics['heatmap_total']} scheduled appointments; color scale 0 to current snapshot maximum.",
               "histogram":f"n = {metrics['duration_record_count']} session records; eight 10-min bins; mean from raw durations.",
               "overview":f"a: {data['range']} days ({metrics['support_count']} activities); b: {metrics['risk_observation_count']} risk observations; "
                          f"c: {metrics['heatmap_total']} appointments; d: {metrics['duration_record_count']} session records."}[kind]
    lines = [f"SYNTHETIC DESIGN EXAMPLE | Sample {data['sample']} | {start} to {end} (UTC)",context,
             "Source: docs/design/chart-demo-data.js | Counts are not unique people. No uncertainty or significance inferred."]
    fig.text(0.06,0.025,"\n".join(lines),ha="left",va="bottom",fontsize=7.2,linespacing=1.5)


def audit_export(fig, path, size, dpi):
    """Check visible text stays inside fixed canvas, and all formats are genuine."""
    import matplotlib.pyplot as plt
    from matplotlib.text import Text
    from PIL import Image
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        bounds = fig.bbox
        clipped = []
        inactive_tick_labels = set()
        # Locators may create ticks beyond the current limits; Matplotlib does
        # not draw those labels, although findobj still returns their Text.
        for ax in fig.axes:
            for axis in (ax.xaxis, ax.yaxis):
                low,high = sorted(axis.get_view_interval())
                for tick in axis.get_major_ticks() + axis.get_minor_ticks():
                    if tick.get_loc() < low or tick.get_loc() > high:
                        inactive_tick_labels.update((tick.label1,tick.label2))
        for artist in fig.findobj(match=Text):
            if artist in inactive_tick_labels or not artist.get_visible() or not artist.get_text().strip():
                continue
            box = artist.get_window_extent(renderer)
            if box.width and box.height and (box.x0 < bounds.x0-1 or box.y0 < bounds.y0-1 or box.x1 > bounds.x1+1 or box.y1 > bounds.y1+1):
                clipped.append(artist.get_text())
        require(not clipped,"Text outside figure canvas: " + "; ".join(clipped[:4]))
        for extension in ("svg","pdf","png"):
            fig.savefig(path.with_suffix("."+extension),dpi=dpi)
        glyph_warnings = [str(w.message) for w in seen if "Glyph" in str(w.message) and "missing" in str(w.message)]
        require(not glyph_warnings,"Missing font glyphs detected: " + "; ".join(glyph_warnings))
    svg_path = path.with_suffix(".svg")
    tree = ET.parse(svg_path)
    require(bool(tree.findall(".//{http://www.w3.org/2000/svg}path")),"SVG has no vector paths.")
    require(not tree.findall(".//{http://www.w3.org/2000/svg}image"),"SVG unexpectedly embeds a raster image.")
    pdf_content = path.with_suffix(".pdf").read_bytes()
    require(pdf_content.startswith(b"%PDF-"),"Invalid PDF signature.")
    require(b"/Subtype /Type3" not in pdf_content,"PDF contains Type3 fonts.")
    require(b"/FontFile2" in pdf_content,"PDF TrueType font embedding not found.")
    with Image.open(path.with_suffix(".png")) as image:
        expected = tuple(round(dimension*dpi) for dimension in size)
        require(image.size == expected,"PNG dimensions differ from fixed figure size.")
        png_dpi = image.info.get("dpi",(0,0))
        require(all(abs(value-dpi)<0.1 for value in png_dpi),"PNG DPI metadata mismatch.")
        grayscale = path.with_name(path.name+"-grayscale").with_suffix(".png")
        image.convert("L").save(grayscale,dpi=(dpi,dpi))
    plt.close(fig)
    return {"basename":path.name,"size_inches":list(size),"dpi":dpi,"png_pixels":list(expected),
            "png_embedded_dpi":list(png_dpi),"text_within_canvas":True,"missing_glyph_warnings":0,
            "svg_vector_paths":True,"svg_embedded_raster":False,"pdf_truetype_embedded":True,
            "files":[{"path":str(p.relative_to(path.parent)),"sha256":digest(p.read_bytes()),"bytes":p.stat().st_size}
                     for p in [path.with_suffix(".svg"),path.with_suffix(".pdf"),path.with_suffix(".png"),grayscale]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--range",type=int,choices=(7,14,30),default=14)
    parser.add_argument("--sample",choices=("A","B"),default="A")
    parser.add_argument("--output",type=Path,default=ROOT/"tmp/scientific-figures",help="Parent directory; a fresh run subdirectory is created.")
    parser.add_argument("--palette",type=Path,default=PALETTE)
    parser.add_argument("--input",type=Path,help="Prior input-data.json generated by this script; range/sample must match.")
    parser.add_argument("--node",default="node",help="Node executable name/path.")
    parser.add_argument("--style",choices=("builtin","science"),default="builtin")
    args = parser.parse_args()
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy
        import PIL
    except ImportError as error:
        parser.exit(2,f"Missing plotting dependency ({error.name}). Use an existing Python with matplotlib/numpy/Pillow; no packages were installed.\n")
    try:
        palette,palette_hash = load_palette(args.palette.resolve())
        fixtures,node_version = source_fixtures(args.node)
        checks = [validate_data(fixture) for fixture in fixtures]
        chosen = next(fixture for fixture in fixtures if fixture["range"] == args.range and fixture["sample"] == args.sample)
        input_kind = "node-imported-existing-generator"
        external_input_hash = None
        if args.input:
            raw_input = args.input.read_bytes()
            package = json.loads(raw_input)
            require(package.get("schema") == SCHEMA and package.get("synthetic") is True,"--input must be an input-data.json generated by this script.")
            require(encoded(package["data"]) == encoded(chosen),"--input differs from the selected current generator fixture; select matching --range/--sample.")
            chosen = package["data"]
            input_kind = "verified-synthetic-fixture-file"
            external_input_hash = digest(raw_input)
        metrics = validate_data(chosen)
        style = configure_style(args.style,palette)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = args.output.resolve()/f"{stamp}-{args.range}d-{args.sample}"
        output.mkdir(parents=True,exist_ok=False)
        package = {"schema":SCHEMA,"synthetic":True,"data":chosen}
        write_json(output/"input-data.json",package)
        files = []
        for kind in ("trend","risk","heatmap","histogram"):
            size = (7.2,4.8)
            fig,ax = plt.subplots(figsize=size,dpi=100)
            fig.subplots_adjust(left=0.12,right=0.94,top=0.86,bottom=0.27)
            draw_panel(kind,fig,ax,chosen,palette,metrics)
            add_caption(fig,chosen,kind,metrics)
            files.append(audit_export(fig,output/kind,size,300))
        size = (10.0,8.0)
        fig,axes = plt.subplots(2,2,figsize=size,dpi=100)
        fig.subplots_adjust(left=0.09,right=0.94,top=0.90,bottom=0.21,wspace=0.43,hspace=0.58)
        for label,kind,ax in zip("abcd",("trend","risk","heatmap","histogram"),axes.flat):  # noqa: B905
            draw_panel(kind,fig,ax,chosen,palette,metrics,compact=True)
            ax.text(-0.16,1.12,label,transform=ax.transAxes,fontweight="bold",fontsize=11)
        fig.suptitle("Synthetic support-activity figure collection",x=0.09,ha="left",fontsize=13,fontweight="bold")
        add_caption(fig,chosen,"overview",metrics)
        files.append(audit_export(fig,output/"overview",size,300))
        manifest = {"schema":"xinyu-scientific-export-v1","created_utc":datetime.now(timezone.utc).isoformat(),
            "synthetic":True,"range_days":args.range,"sample":args.sample,"source_date_range_utc":[chosen["daily"][0]["date"],chosen["daily"][-1]["date"]],
            "input":{"kind":input_kind,"path":"input-data.json","sha256":digest((output/"input-data.json").read_bytes()),
                     "canonical_data_sha256":digest(encoded(chosen)),"external_input_sha256":external_input_hash,
                     "generator":"docs/design/chart-demo-data.js","generator_sha256":digest(GENERATOR.read_bytes()),
                     "generator_import_sha256":digest((ROOT/"src/styles/echarts-theme.js").read_bytes())},
            "shared_palette":{"path":str(args.palette.resolve()),"sha256":palette_hash,"name":palette.get("name"),"version":palette.get("version")},
            "method":{"description":"Direct daily sums and counts; raw-record arithmetic mean; no fitted model, error bars or p-values.",
                      "histogram":"8 bins [0,10),...,[70,80), counted from raw session durations.",
                      "heatmap":"28 weekday/time-slot sums; shared sequential palette; scale 0 to snapshot maximum.",
                      "denominators":"Support activities, risk observations, planned appointments and duration records are distinct counts, not unique people.",
                      "style":style,"font":"DejaVu Sans","minimum_text_size_pt":7.2,"latex":False},
            "runtime":{"python":sys.version.split()[0],"matplotlib":matplotlib.__version__,"numpy":numpy.__version__,"Pillow":PIL.__version__,"node":node_version},
            "export_script_sha256":digest(Path(__file__).read_bytes()),
            "selected_checks":metrics,"six_fixture_checks":checks,"figures":files,
            "limitations":["Synthetic display fixtures support no population, treatment, significance or causal conclusions.",
                            "Generic scientific presentation; no universal SCI template or journal compliance claim.",
                            "Shared sequential color ramp is not certified perceptually uniform; values and colorbar remain explicit.",
                            "SVG text stays editable and needs the named font; PDF embeds TrueType.",
                            "Automatic checks cover file integrity, glyph warnings and canvas bounds; visual review remains necessary."]}
        write_json(output/"manifest.json",manifest)
        print(json.dumps({"status":"passed","output":str(output),"style":style,"figures":len(files),"fixture_checks":len(checks)},ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError, StopIteration, subprocess.SubprocessError) as error:
        parser.exit(1,"Export failed: " + str(error) + "\n")


if __name__ == "__main__":
    main()
