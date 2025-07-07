from flask import Flask, render_template
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/promotions")
def promotions():
    return render_template(
        "promotions.html",
        promotion_code="P0472022",
        user_name="Daniel Zhang",
        owners=[...],
        selected_owner="All",
        search_query="",
        active_tab="RDC",
        promotions=[{
            "code": "P0472022",
            "orbit_id": "O123456",
            "status": "Active",
            "description": "Promotion Description",
            "start_date": "2022-01-01",
            "end_date": "2022-12-31",
            "owner": "Daniel Zhang"
        }],
        current_datetime=datetime.now().strftime("%A, %B %d, %Y %I:%M:%S %p")
    )



if __name__ == "__main__":
    app.run(debug=True)
