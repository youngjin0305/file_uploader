from flask import Flask, request, jsonify, send_from_directory
from flask_pymongo import PyMongo
from flask_cors import CORS
from dotenv import load_dotenv
from bson import ObjectId
from datetime import datetime
import base64
import os

load_dotenv()

app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*"}})

mongo_uri = os.getenv("MONGO_URI")
app.config["MONGO_URI"] = mongo_uri
mongo = PyMongo(app)
db = mongo.db.files

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def human_readable_size(size_in_bytes):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024


# 1. 파일 업로드 엔드포인트
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file:
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(file_path)
        upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        file_id = db.insert_one(
            {
                "file_name": file.filename,
                "file_type": request.form.get("file_type", ""),
                "content_type": file.content_type,
                "path": file_path,
                "description": request.form.get("description", ""),
                "uploaded_at": upload_time,
            }
        ).inserted_id

        return (
            jsonify({"message": "파일 업로드 성공!", "file_id": str(file_id)}),
            201,
        )


# 2. 파일 목록 조회 엔드포인트
@app.route("/files", methods=["GET"])
def list_files():
    files = []
    for file in db.find():
        file_size = os.path.getsize(file["path"])
        readable_size = human_readable_size(file_size)
        files.append(
            {
                "id": str(file["_id"]),
                "file_name": file["file_name"],
                "file_type": file["file_type"],
                "uploaded_at": file["uploaded_at"],
                "file_size": readable_size,
            }
        )
    return jsonify(files), 200


# 3. 파일 세부 정보 조회 엔드포인트
@app.route("/files/<file_id>", methods=["GET"])
def get_file(file_id):
    try:
        file = db.find_one({"_id": ObjectId(file_id)})
    except:
        return jsonify({"error": "Invalid file ID"}), 400
    if file["content_type"] == "image/jpeg" or file["content_type"] == "image/png":
        file_path = file["path"]
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
    else:
        encoded_string = ""
    file_size = os.path.getsize(file["path"])
    readable_size = human_readable_size(file_size)
    if file:
        return (
            jsonify(
                {
                    "id": str(file["_id"]),
                    "file_name": file["file_name"],
                    "file_type": file["file_type"],
                    "description": file["description"],
                    "file_size": readable_size,
                    "uploaded_at": file["uploaded_at"],
                    "image_data": encoded_string,
                }
            ),
            200,
        )
    else:
        return jsonify({"error": "File not found"}), 404


# 4. 파일 설명 수정 엔드포인트
@app.route("/files/<file_id>", methods=["PATCH"])
def update_file_description(file_id):
    try:
        # 요청에서 JSON 데이터를 가져옵니다.
        data = request.get_json()
        if not data or "description" not in data:
            return jsonify({"error": "설명이 제공되지 않았습니다."}), 400

        new_description = data["description"]

        # 파일 ID를 ObjectId로 변환하고 해당 파일을 찾습니다.
        result = db.update_one(
            {"_id": ObjectId(file_id)},
            {"$set": {"description": new_description}}
        )

        if result.matched_count == 0:
            return jsonify({"error": "파일을 찾을 수 없습니다."}), 404

        return jsonify({"message": "파일 설명이 성공적으로 업데이트되었습니다!"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 5. 파일 다운로드 엔드포인트
@app.route("/download/<file_id>", methods=["GET"])
def download_file(file_id):
    file = db.find_one({"_id": ObjectId(file_id)})
    if file:
        return send_from_directory(
            app.config["UPLOAD_FOLDER"],
            file["file_name"],
            as_attachment=True,
            download_name=file["file_name"],
        )
    else:
        return jsonify({"error": "파일을 찾을 수 없습니다"}), 404


# 6. 파일 삭제 엔드포인트
@app.route("/files/<file_id>", methods=["DELETE"])
def delete_file(file_id):
    file = db.find_one({"_id": ObjectId(file_id)})
    if file:
        os.remove(file["path"])  # 파일 삭제
        db.delete_one({"_id": ObjectId(file_id)})  # DB에서 파일 정보 삭제
        return jsonify({"message": "파일이 정상적으로 삭제되었습니다!"}), 200
    return jsonify({"error": "파일을 찾을 수 없습니다."}), 404


if __name__ == "__main__":
    app.run(debug=True)
