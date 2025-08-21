from flask import Flask, render_template, redirect, request, jsonify, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import razorpay

# --- Flask App Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'a-very-secret-and-random-key-for-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:root123@localhost/parking_slots?ssl_disabled=True'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Razorpay Setup ---
RAZORPAY_KEY_ID = "rzp_test_dNrnGiyXcjb2ug"
RAZORPAY_KEY_SECRET = "RhMVJPhdBulIdw41Eq9TZcCm"
client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# --- Global variables for dynamic location ---
esp_lat = None
esp_lng = None
nearby_zones = []

# --- Database Models ---
class Location_of_slots(db.Model):
    __tablename__ = 'location_of_slots'
    slot_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    location = db.Column(db.String(50))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    available_slots = db.Column(db.Integer)
    occupied_slots = db.Column(db.Integer)

class UserConcerns(db.Model):
    __tablename__ = 'user_concerns'
    concern_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_email = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

# --- Dynamic location update route ---
@app.route('/update_location', methods=['POST'])
def update_location():
    """API to receive latest lat/lng from ESP32/NavIC."""
    global esp_lat, esp_lng
    try:
        data = request.get_json(force=True)
        lat = data.get("lat")
        lng = data.get("lng")
        if lat is None or lng is None:
            return jsonify({"error": "Missing lat or lng"}), 400
        esp_lat = float(lat)
        esp_lng = float(lng)
        return jsonify({"message": "Location updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_latest_location')
def get_latest_location():
    """Return the latest stored coordinates."""
    return jsonify({"lat": esp_lat, "lng": esp_lng})

# --- Payment ---
@app.route('/create_order', methods=['POST'])
def create_order():
    data = request.get_json()
    amount = float(data.get("amount", 0))
    payment_type = data.get("vehicle")

    amount_paise = int(amount * 100) if amount < 1000 else int(amount)
    order = client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": 1
    })
    return jsonify({
        "order_id": order['id'],
        "key_id": RAZORPAY_KEY_ID,
        "amount": amount_paise,
        "currency": "INR",
        "vehicle": payment_type
    })

# --- Home Page ---
@app.route('/', methods=['GET', 'POST'])
def index():
    """Show nearby parking slots based on latest dynamic location."""
    global esp_lat, esp_lng, nearby_zones
    radius_km = None
    nearby_slots = []
    if request.method == 'POST':
        radius_input = request.form.get('radius')
        if radius_input :
            try:
                radius_m = float(radius_input)
                if radius_m <= 0:
                    flash("Radius must be positive.", "error")
                    return redirect(url_for("index"))
                radius_km = radius_m / 1000.0
                query = """
                    SELECT slot_id, location, latitude, longitude, available_slots, occupied_slots,
                           (6371 * ACOS(COS(RADIANS(:lat)) * COS(RADIANS(latitude)) *
                           COS(RADIANS(longitude) - RADIANS(:lng)) +
                           SIN(RADIANS(:lat)) * SIN(RADIANS(latitude)))) AS distance_m
                    FROM location_of_slots
                    HAVING distance_m < :radius_km
                    ORDER BY distance_m ASC
                """
                result = db.session.execute(text(query), {
                    "lat": esp_lat,
                    "lng": esp_lng,
                    "radius_km": radius_km
                })
                nearby_slots = result.fetchall()
                nearby_zones = nearby_slots
            except ValueError:
                flash("Invalid radius value.", "error")

    return render_template('index.html', slots=nearby_slots, lat=esp_lat, lng=esp_lng, radius_km=radius_km)

# --- Map Page ---
@app.route('/map')
def map_view():
    dest_lat = request.args.get('lat')
    dest_lng = request.args.get('lng')
    zone_id = request.args.get('zone_id')
    zone = Location_of_slots.query.get_or_404(zone_id)
    city_rates = {'car': 40, 'bike': 20}
    return render_template('map.html',
                           dest_lat=dest_lat,
                           dest_lng=dest_lng,
                           user_lat=esp_lat,
                           user_lng=esp_lng,
                           slots=nearby_zones,
                           selected_zone=zone,
                           city_rates=city_rates)

# --- Contact ---
@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        user_email = request.form.get("email")
        message = request.form.get("message")

        if user_email and message:
            new_concern = UserConcerns(user_email=user_email, message=message)
            db.session.add(new_concern)
            db.session.commit()
            flash("Your message has been sent successfully!", "success")
            return redirect(url_for("contact"))
        else:
            flash("Please fill in all required fields.", "error")

    return render_template("contact.html")

@app.route("/about")
def about():
    return render_template('about.html')

# --- Authentication ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'password':
            session['logged_in'] = True
            flash('You were successfully logged in!', 'success')
            return redirect(url_for('admin_page'))
        else:
            flash('Invalid credentials. Please try again.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You have been successfully logged out.', 'success')
    return redirect(url_for('index'))

@app.route('/admin')
def admin_page():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('admin.html')

# --- CRUD APIs ---
@app.route('/api/slots', methods=['GET'])
def get_all_slots():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    search_term = request.args.get('search', '').strip()
    if not search_term:
        return jsonify([])
    query_pattern = f"%{search_term}%"
    slots = Location_of_slots.query.filter(Location_of_slots.location.ilike(query_pattern)).order_by(Location_of_slots.slot_id).all()
    return jsonify([{
        'slot_id': s.slot_id,
        'location': s.location,
        'latitude': s.latitude,
        'longitude': s.longitude,
        'available_slots': s.available_slots,
        'occupied_slots': s.occupied_slots
    } for s in slots])

@app.route('/api/slots/<int:slot_id>', methods=['GET'])
def get_slot(slot_id):
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    slot = Location_of_slots.query.get_or_404(slot_id)
    return jsonify({
        'slot_id': slot.slot_id,
        'location': slot.location,
        'latitude': slot.latitude,
        'longitude': slot.longitude,
        'available_slots': slot.available_slots,
        'occupied_slots': slot.occupied_slots
    })

@app.route('/api/slots', methods=['POST'])
def create_slot():
    if not session.get('logged_in'):
        flash('Unauthorized access. Please log in first.', 'error')
        return redirect(url_for('login'))
    try:
        data = request.get_json()
        new_slot = Location_of_slots(
            location=data['location'],
            latitude=float(data['latitude']),
            longitude=float(data['longitude']),
            available_slots=int(data['available_slots']),
            occupied_slots=int(data['occupied_slots'])
        )
        db.session.add(new_slot)
        db.session.commit()
        return jsonify({'message': 'Slot created successfully', 'slot_id': new_slot.slot_id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/slots/<int:slot_id>', methods=['PUT'])
def update_slot(slot_id):
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    slot = Location_of_slots.query.get_or_404(slot_id)
    data = request.get_json()
    slot.location = data.get('location', slot.location)
    slot.latitude = float(data.get('latitude', slot.latitude))
    slot.longitude = float(data.get('longitude', slot.longitude))
    slot.available_slots = int(data.get('available_slots', slot.available_slots))
    slot.occupied_slots = int(data.get('occupied_slots', slot.occupied_slots))
    db.session.commit()
    return jsonify({'message': 'Slot updated successfully'})

@app.route('/api/slots/<int:slot_id>', methods=['DELETE'])
def delete_slot(slot_id):
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    slot = Location_of_slots.query.get_or_404(slot_id)
    db.session.delete(slot)
    db.session.commit()
    return jsonify({'message': 'Slot deleted successfully'})

@app.route('/admin/concerns')
def admin_concerns():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    concerns = UserConcerns.query.order_by(UserConcerns.submitted_at.desc()).all()
    return render_template('concerns.html', concerns=concerns)

# --- Main execution ---
if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True,port=5000)
