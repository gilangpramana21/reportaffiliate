from flask import Blueprint, render_template, request, jsonify, abort
import json

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    return render_template("index.html")


@pages_bp.route("/configure")
def configure():
    return render_template("configure.html")


@pages_bp.route("/brand-selection")
def brand_selection():
    """
    Brand selection page for multi-brand report generation.
    
    Expected URL parameters:
    - parse_id: ID of the parsed data
    - brand_data: JSON string containing brand selection data
    """
    parse_id = request.args.get('parse_id')
    brand_data_json = request.args.get('brand_data')
    
    if not parse_id or not brand_data_json:
        abort(400, "Missing required parameters: parse_id and brand_data")
    
    try:
        brand_data = json.loads(brand_data_json)
    except json.JSONDecodeError:
        abort(400, "Invalid brand_data JSON")
    
    return render_template("brand_selection.html", 
                         parse_id=parse_id,
                         brand_data=brand_data)


@pages_bp.route("/history")
def history():
    return render_template("history.html")


@pages_bp.route("/brands")
def brands_page():
    return render_template("brands.html")


@pages_bp.route("/terms")
def terms():
    return render_template("terms.html")


@pages_bp.route("/privacy")
def privacy():
    return render_template("privacy.html")


@pages_bp.route("/settings")
def settings():
    return render_template("settings.html")


@pages_bp.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")
