import datetime
import os
import pandas as pd
from flask import Flask, render_template, redirect, request, jsonify, session, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, exc
import razorpay
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from geopy.geocoders import Nominatim
import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name="dgpahvl9m",
    api_key="397185777883491",
    api_secret="edsJwdE-mzTcqsAKoLetcymYarM"
)


# --- Flask App Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-default-local-secret-key')

# --- Database Setup ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- File Uploads ---
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

# --- Razorpay Setup ---
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET')
client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
else:
    app.logger.warning("⚠️ Razorpay keys missing; payment routes will not work.")

# ===================================================================
# --- CSV Import Helper (runs only if enabled) ---
# ===================================================================
def import_csvs_if_needed():
    base_dir = os.path.join(os.path.dirname(__file__), "static", "data")
    csv_mappings = {
        "location_of_slots.csv": "location_of_slots",
        "user_applications.csv": "user_applications",
        "user_concerns.csv": "user_concerns"
    }

    for file_name, table_name in csv_mappings.items():
        file_path = os.path.join(base_dir, file_name)
        if not os.path.exists(file_path):
            app.logger.info(f"CSV {file_name} not found — skipping {table_name}")
            continue

        try:
            count = db.session.execute(text(f"SELECT COUNT(1) FROM {table_name}")).scalar()
            if count and int(count) > 0:
                app.logger.info(f"{table_name} already has {count} rows — skipping import.")
                continue

            df = pd.read_csv(file_path, encoding="latin1")
            df.to_sql(table_name, db.engine, if_exists="append", index=False)
            app.logger.info(f"✅ Imported {len(df)} rows into {table_name}")
        except Exception as e:
            app.logger.exception(f"❌ Failed to import {file_name}: {e}")
            db.session.rollback()

# ===================================================================
# --- Helper Functions ---
# ===================================================================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ===================================================================
# --- Database Models ---
# ===================================================================
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

class UserApplication(db.Model):
    __tablename__ = 'user_applications'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    # --- Application Details ---
    owner_name = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    location_link = db.Column(db.String(512), nullable=True)
    slot_count = db.Column(db.Integer, nullable=True)
    security_level = db.Column(db.String(50), nullable=True)
    price_per_hour = db.Column(db.Numeric(10, 2), nullable=True)
    govt_id_path = db.Column(db.String(255), nullable=True)
    property_proof_path = db.Column(db.String(255), nullable=True)
    zone_photo_path = db.Column(db.String(255), nullable=True)
    declaration_agreed = db.Column(db.Boolean, nullable=True)
    status = db.Column(db.String(50), nullable=True, default=None)
    submission_date = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<UserApplication {self.id} by {self.username}>"
# ===================================================================
# ▼▼▼ CIVILIAN USER ROUTES ▼▼▼
# ===================================================================

@app.route("/Civilian_Signup", methods=["GET", "POST"])
def Civilian_Signup():
    if request.method == "POST":
        email = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]

        existing_user = UserApplication.query.filter(
            (UserApplication.email == email) | (UserApplication.username == username)
        ).first()

        if existing_user:
            flash("Email or Username already exists!", "error")
            return redirect(url_for("Civilian_Signup"))

        hashed_password = generate_password_hash(password)
        new_user = UserApplication(email=email, username=username, password=hashed_password)
        db.session.add(new_user)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.exception("DB commit failed: %s", e)
            flash("Internal error. Please try again.", "error")

        flash("Account created successfully! Please login.", "success")
        return redirect(url_for("Civilian_login"))
    return render_template("Civilian_Signup.html")

@app.route("/Civilian_login", methods=["GET", "POST"])
def Civilian_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = UserApplication.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['logged_in'] = True
            flash("Login successful!", "success")
            return redirect(url_for("Civilian_home"))
        else:
            flash("Invalid email or password", "error")
    return render_template("Civilian_login.html")

@app.route('/Civilian_home')
def Civilian_home():
    if not session.get('logged_in'):
        flash('Please log in first.', 'error')
        return redirect(url_for('Civilian_login'))
    return render_template('Civilian_home.html')

@app.route('/application_status')
def Status():
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('Civilian_login'))

    user_id = session['user_id']
    user_application = UserApplication.query.get(user_id)  # fetch row by primary key
    applications = [user_application] if user_application else []  # wrap in list for template

    return render_template("application_status.html", applications=applications)


@app.route('/submit_parking_zone', methods=['POST'])
def submit_parking_zone():
    if 'user_id' not in session:
        flash('You must be logged in to submit an application.', 'error')
        return redirect(url_for('Civilian_login'))

    user_application = db.session.get(UserApplication, session['user_id'])
    if not user_application:
        flash('User not found. Please log in again.', 'error')
        return redirect(url_for('Civilian_login'))

    if request.method == 'POST':
        try:
            govt_id_file = request.files['govt_id']
            property_proof_file = request.files['property_proof']
            zone_photo_file = request.files['zone_photo']

            if not all([govt_id_file, property_proof_file, zone_photo_file]):
                flash('Please upload all required documents.', 'error')
                return redirect(url_for('get_started'))

            if allowed_file(govt_id_file.filename) and \
               allowed_file(property_proof_file.filename) and \
               allowed_file(zone_photo_file.filename):
                
                govt_id_upload = cloudinary.uploader.upload(govt_id_file, folder="parking_zone_docs", resource_type="auto")
                property_proof_upload = cloudinary.uploader.upload(property_proof_file, folder="parking_zone_docs", resource_type="auto")
                zone_photo_upload = cloudinary.uploader.upload(zone_photo_file, folder="parking_zone_docs", resource_type="auto")


                user_application.owner_name = request.form['owner_name']
                user_application.phone = request.form['phone']
                user_application.address = request.form['address']
                user_application.location_link = request.form['location_link']
                user_application.slot_count = int(request.form['slot_count'])
                user_application.security_level = request.form['security_level']
                user_application.price_per_hour = float(request.form['price'])
                user_application.declaration_agreed = 'declaration' in request.form

                user_application.govt_id_path = govt_id_upload['secure_url']
                user_application.property_proof_path = property_proof_upload['secure_url']
                user_application.zone_photo_path = zone_photo_upload['secure_url']
                user_application.status = 'pending'
                user_application.submission_date = datetime.datetime.utcnow()

                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    app.logger.exception("DB commit failed: %s", e)
                    flash("Internal error. Please try again.", "error")

                flash('Your application has been submitted successfully!', 'success')
                return redirect(url_for('Civilian_home'))
            else:
                flash('Invalid file type. Please upload PNG, JPG, or PDF files.', 'error')
                return redirect(url_for('get_started'))

        except Exception as e:
            db.session.rollback()
            print(f"An error occurred: {e}")
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('get_started'))
    return redirect(url_for('get_started'))

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/applications/<int:app_id>/<action>', methods=['POST'], endpoint='handle_application')
def handle_application(app_id, action):
    application = UserApplication.query.get_or_404(app_id)

    if action == 'approve':
        application.status = 'approved'
    elif action == 'reject':
        application.status = 'rejected'
    else:
        flash('Invalid action', 'error')
        return redirect(url_for('applications'))

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.exception("DB commit failed: %s", e)
        flash("Internal error. Please try again.", "error")
    flash(f"Application {action}d successfully!", 'success')
    return redirect(url_for('applications'))

@app.route('/update_location', methods=['POST'])
def update_location():
    global esp_lat, esp_lng
    try:
        data = request.get_json(force=True)
        lat = data.get("lat")
        lng = data.get("lng")
        if lat is None or lng is None:
            return jsonify({"error": "Missing lat or lng"}), 400
        esp_lat = float(lat)
        esp_lng = float(lng)
        print("Received data:", data)
        return jsonify({"message": "Location updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_latest_location')
def get_latest_location():
    global esp_lat,esp_lng
    return jsonify({"lat": esp_lat, "lng": esp_lng})

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

# esp_lat, esp_lng = 12.90732, 77.60590
# # location finding 
# geolocator = Nominatim(user_agent="ParkingFinderApp_vinay_2025")

# # Coordinates
# latitude = esp_lat
# longitude = esp_lng

# # Reverse geocode
# location_obj = geolocator.reverse((latitude, longitude), language='en')
# User_location = location_obj.address if location_obj else "Location not found"

# @app.route('/User', methods=['GET', 'POST'])
# def User():
#     global esp_lat, esp_lng, nearby_zones
#     esp_lat, esp_lng = 12.90732, 77.60590
#     curr_lat, curr_lng = esp_lat, esp_lng
#     radius_km = None
#     nearby_slots = []

#     if request.method == 'POST':
#         radius_input = request.form.get('radius')
#         if radius_input:
#             try:
#                 radius_m = float(radius_input)
#                 if radius_m <= 0:
#                     flash("Radius must be positive.", "error")
#                     return redirect(url_for("User"))

#                 radius_km = radius_m / 1000.0  # convert meters to km

#                 # PostgreSQL-compatible query using a subquery to filter by distance
#                 query = """
#                     SELECT *
#                     FROM (
#                         SELECT slot_id, location, latitude, longitude, available_slots, occupied_slots,
#                                (6371 * ACOS(
#                                    LEAST(1.0, COS(RADIANS(:lat)) * COS(RADIANS(latitude)) *
#                                    COS(RADIANS(longitude) - RADIANS(:lng)) +
#                                    SIN(RADIANS(:lat)) * SIN(RADIANS(latitude)))
#                                )) AS distance_km
#                         FROM location_of_slots
#                     ) AS sub
#                     WHERE distance_km < :radius_km
#                     ORDER BY distance_km ASC;
#                 """

#                 result = db.session.execute(
#                     text(query),
#                     {"lat": curr_lat, "lng": curr_lng, "radius_km": radius_km}
#                 )
#                 nearby_slots = result.fetchall()
#                 nearby_zones = nearby_slots

#                 if not nearby_slots:
#                     flash("No slots found within this radius.", "info")

#             except ValueError:
#                 flash("Invalid radius value.", "error")
#             except Exception as e:
#                 flash(f"Error fetching nearby slots: {e}", "error")

#     return render_template(
#         'User.html',
#         slots=nearby_slots,
#         lat=curr_lat,
#         lng=curr_lng,
#         radius_km=(radius_km * 1000 if radius_km else None),User_location=User_location
#     )

# @app.route('/map')
# def map_view():
#     try:
#         # Convert query params to float/int
#         dest_lat = float(request.args.get('lat', 0))
#         dest_lng = float(request.args.get('lng', 0))
#         zone_id = int(request.args.get('zone_id', 0))

#         # Get the selected parking zone
#         zone = Location_of_slots.query.get_or_404(zone_id)

#         # Example city rates
#         city_rates = {'car': 40, 'bike': 20}

#         # User location (temporary fixed coordinates)
#         esp_lat = 12.90732
#         esp_lng = 77.60590

#         return render_template(
#             'map.html',
#             dest_lat=dest_lat,
#             dest_lng=dest_lng,
#             user_lat=esp_lat,
#             user_lng=esp_lng,
#             slots=nearby_zones,          # consider passing only relevant slots
#             selected_zone=zone,
#             city_rates=city_rates
#         )
#     except Exception as e:
#         flash(f"Error loading map: {e}", "error")
#         return redirect(url_for("User"))

@app.route('/Driver', methods=['GET', 'POST'])
def Driver():
    # --- Configuration ---
    # It's better to get these from a config file or environment variables
    # For now, we'll use the hardcoded values.
    # IMPORTANT: Do NOT commit real API keys to your code.
    GMAPS_API_KEY = os.environ.get("GMAPS_API_KEY", "YOUR_FALLBACK_API_KEY_HERE")
    
    # Static coordinates for the user's location (e.g., from an ESP32)
    user_lat, user_lng = 12.90732, 77.60590
    
    # Default search radius in kilometers
    default_radius_km = 2.0
    
    # --- Initialization ---
    nearby_slots_data = []
    user_location_address = "Location not available"

    # --- Geocoding: Get user's address from coordinates ---
    try:
        # It's good practice to set a user_agent
        geolocator = Nominatim(user_agent="smart_parking_app/1.0")
        location_obj = geolocator.reverse((user_lat, user_lng), language='en')
        
        if location_obj and location_obj.address:
            # Create a shorter, more readable address
            address_parts = location_obj.address.split(",")
            user_location_address = ", ".join(part.strip() for part in address_parts[:4])
        else:
            user_location_address = "Address not found for coordinates"
            
    except Exception as e:
        app.logger.error(f"Geocoding (Nominatim) error: {e}")
        user_location_address = "Error fetching address"

    # --- Database Query: Find nearby parking slots ---
    try:
        # ✅ FIX: This query uses a subquery to allow filtering by the 'distance_km' alias.
        # This is the standard and correct way to do this in PostgreSQL.
        query = text("""
            SELECT * FROM (
                SELECT 
                    slot_id, location, latitude, longitude, available_slots, occupied_slots,
                    (6371 * ACOS(
                        LEAST(1.0, -- Clamp value to 1.0 to avoid domain errors
                            COS(RADIANS(:lat)) * COS(RADIANS(latitude)) *
                            COS(RADIANS(longitude) - RADIANS(:lng)) +
                            SIN(RADIANS(:lat)) * SIN(RADIANS(latitude))
                        )
                    )) AS distance_km
                FROM 
                    location_of_slots
            ) AS calculated_distances
            WHERE 
                distance_km <= :radius_km
            ORDER BY 
                distance_km ASC;
        """)

        result = db.session.execute(
            query,
            {"lat": user_lat, "lng": user_lng, "radius_km": default_radius_km}
        )
        
        # This part remains the same
        nearby_slots_data = [dict(row._mapping) for row in result]

    except Exception as e:
        app.logger.error(f"Database error while fetching nearby slots: {e}")
        flash("Could not retrieve parking locations due to a server error.", "error")

    # --- Render Template ---
    return render_template(
        'Driver.html',
        slots=nearby_slots_data,
        lat=user_lat,
        lng=user_lng,
        User_location=user_location_address,
        api_key="AIzaSyAqyzQZLE0TvmXnqNcII65Edvu71PV-HCI"
    )

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        user_email = request.form.get("email")
        message = request.form.get("message")
        if user_email and message:
            new_concern = UserConcerns(user_email=user_email, message=message)
            db.session.add(new_concern)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.exception("DB commit failed: %s", e)
                flash("Internal error. Please try again.", "error")
            flash("Your message has been sent successfully!", "success")
            return redirect(url_for("contact"))
        else:
            flash("Please fill in all required fields.", "error")
    return render_template("contact.html")

@app.route("/about")
def about():
    return render_template('about.html')

@app.route("/get_started")
def get_started():
    if 'user_id' not in session:
        flash('You must be logged in to start an application.', 'error')
        return redirect(url_for('Civilian_login'))
    user = db.session.get(UserApplication, session['user_id'])
    return render_template("get_started.html", user=user)

@app.route("/applications")
def applications():
    if not session.get('logged_in'):
        flash('Please log in first.', 'error')
        return redirect(url_for('login'))
    
    all_applications = UserApplication.query.order_by(UserApplication.submission_date.desc()).all()
    return render_template('applications.html', applications=all_applications)

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
    return redirect(url_for('Civilian_login'))

@app.route('/admin')
def admin_page():
    if not session.get('logged_in'):
        flash('Please log in to view the admin dashboard.', 'error')
        return redirect(url_for('login'))
    return render_template('admin.html')


@app.route('/api/slots', methods=['GET'])
def get_all_slots():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    search_term = request.args.get('search', '').strip()
    if not search_term:
        return jsonify([])
    query_pattern = f"%{search_term}%"
    slots = Location_of_slots.query.filter(Location_of_slots.location.ilike(query_pattern)).order_by(Location_of_slots.slot_id).all()
    return jsonify([{'slot_id': s.slot_id, 'location': s.location, 'latitude': s.latitude, 'longitude': s.longitude, 'available_slots': s.available_slots, 'occupied_slots': s.occupied_slots} for s in slots])

@app.route('/api/slots/<int:slot_id>', methods=['GET'])
def get_slot(slot_id):
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    slot = Location_of_slots.query.get_or_404(slot_id)
    return jsonify({'slot_id': slot.slot_id, 'location': slot.location, 'latitude': slot.latitude, 'longitude': slot.longitude, 'available_slots': slot.available_slots, 'occupied_slots': slot.occupied_slots})

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
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.exception("DB commit failed: %s", e)
            flash("Internal error. Please try again.", "error")
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
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.exception("DB commit failed: %s", e)
        flash("Internal error. Please try again.", "error")
    return jsonify({'message': 'Slot updated successfully'})

@app.route('/api/slots/<int:slot_id>', methods=['DELETE'])
def delete_slot(slot_id):
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    slot = Location_of_slots.query.get_or_404(slot_id)
    db.session.delete(slot)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.exception("DB commit failed: %s", e)
        flash("Internal error. Please try again.", "error")
    return jsonify({'message': 'Slot deleted successfully'})

@app.route('/admin/concerns')
def admin_concerns():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    concerns = UserConcerns.query.order_by(UserConcerns.submitted_at.desc()).all()
    return render_template('concerns.html', concerns=concerns)

@app.route('/api/book_slot/<int:slot_id>', methods=['POST'])
def book_slot(slot_id):
    slot = Location_of_slots.query.get_or_404(slot_id)
    if slot.available_slots > 0:
        slot.available_slots -= 1
        slot.occupied_slots += 1
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.exception("DB commit failed: %s", e)
            flash("Internal error. Please try again.", "error")
        return jsonify({'message': 'Slot booked successfully'})
    else:
        return jsonify({'error': 'No available slots'}), 400

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # ensures tables exist
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port,debug=True)  

