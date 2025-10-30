from flask import Blueprint, jsonify
from ai_llm import run_ai_for_cr

ai_bp = Blueprint("ai_bp", __name__)

@ai_bp.route("/ai/run/<int:cr_id>", methods=["POST"])
def ai_run(cr_id):
    data, err = run_ai_for_cr(cr_id)
    if err:
        return jsonify({"error": err}), 404
    return jsonify(data), 200
