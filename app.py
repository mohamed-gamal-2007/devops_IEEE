import os
import secrets
import math
import io
from datetime import datetime
from functools import wraps
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_file
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    current_user,
    login_required
)
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
# ----------------------------------------------------
# 1. App & DB Setup
# ----------------------------------------------------
DB_NAME = 'attendance_system.db'
app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'يرجى تسجيل الدخول للوصول لهذه الصفحة.'
login_manager.login_message_category = 'warning'
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
# ----------------------------------------------------
# 2. Database Models
# ----------------------------------------------------
class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    users = db.relationship('User', backref='department', lazy=True)
class AcademicYear(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    users = db.relationship('User', backref='year', lazy=True)
class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    users = db.relationship('User', backref='section', lazy=True)
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    national_id = db.Column(db.String(14), unique=True, nullable=True)
    age = db.Column(db.Integer, nullable=True)
   
    role = db.Column(db.Integer, default=1, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
   
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    year_id = db.Column(db.Integer, db.ForeignKey('academic_year.id'), nullable=True)
    section_id = db.Column(db.Integer, db.ForeignKey('section.id'), nullable=True)
    # New fields for Staff
    course_name = db.Column(db.String(100), nullable=True) # For Doctors
    supervisor_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True) # For Assistants
   
    # Relationships
    assistants = db.relationship('User', backref=db.backref('supervisor', remote_side=[id]), lazy='dynamic')
    sessions = db.relationship('Session', backref='creator', lazy=True, cascade='all, delete-orphan')
    attendance_records = db.relationship(
        'AttendanceRecord',
        backref='student',
        lazy=True,
        foreign_keys='[AttendanceRecord.student_id]',
        cascade='all, delete-orphan'
    )
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
   
    def get_id(self):
        return str(self.id)
class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_name = db.Column(db.String(150), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
   
    creator_latitude = db.Column(db.Float, nullable=False)
    creator_longitude = db.Column(db.Float, nullable=False)
    max_distance_meters = db.Column(db.Float, default=500.0)
   
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('section.id'), nullable=True)
    attendance_records = db.relationship('AttendanceRecord', backref='session', lazy=True, cascade='all, delete-orphan')
class AttendanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    attendance_time = db.Column(db.DateTime, default=datetime.utcnow)
   
    # Updated fields
    status = db.Column(db.String(20), default='self') # 'self' or 'manual'
    is_manual = db.Column(db.Boolean, default=False) # True if added by doctor/assistant manually
   
    student_latitude = db.Column(db.Float, nullable=True)
    student_longitude = db.Column(db.Float, nullable=True)
    # note column removed
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=False)
   
    manual_by_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    manual_by = db.relationship(
        'User',
        foreign_keys=[manual_by_id],
        backref=db.backref('manual_attendances', lazy=True)
    )
class Excuse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    excuse_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    submission_time = db.Column(db.DateTime, default=datetime.utcnow)
    is_reviewed = db.Column(db.Boolean, default=False)
   
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student = db.relationship('User', backref=db.backref('excuses', cascade='all, delete-orphan'))
   
class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    user = db.relationship('User', backref='activities', foreign_keys=[user_id])
    activity_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    ip_address = db.Column(db.String(50), nullable=True)
# ----------------------------------------------------
# 3. Utility Functions
# ----------------------------------------------------
def add_log(activity_type, description, user_id=None, ip_address=None):
    if ip_address is None:
        try:
            ip = request.remote_addr
        except RuntimeError:
            ip = 'System'
    else:
        ip = ip_address
    log = ActivityLog(
        activity_type=activity_type,
        description=description,
        user_id=user_id,
        ip_address=ip
    )
    db.session.add(log)
    db.session.commit()
def role_required(required_role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if current_user.is_authenticated and current_user.role >= required_role:
                return f(*args, **kwargs)
           
            flash('ليس لديك صلاحية الوصول لهذه الصفحة.', 'danger')
            return redirect(url_for('login'))
        return wrapper
    return decorator
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000
   
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
   
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
   
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
   
    distance = R * c
    return distance
# ----------------------------------------------------
# 4. Initial Setup
# ----------------------------------------------------
def create_initial_data():
    depts = ['AI', 'Cyber Security', 'Data Science']
    for name in depts:
        if not Department.query.filter_by(name=name).first():
            db.session.add(Department(name=name))
   
    years = ['Year 1', 'Year 2', 'Year 3', 'Year 4']
    for name in years:
        if not AcademicYear.query.filter_by(name=name).first():
            db.session.add(AcademicYear(name=name))
    for i in range(1, 16):
        name = f'Section {i}'
        if not Section.query.filter_by(name=name).first():
            db.session.add(Section(name=name))
           
    db.session.commit()
   
    if not User.query.filter_by(role=99).first():
        admin = User(
            first_name='Super',
            last_name='Admin',
            full_name='Super Admin',
            email='admin@univ.com',
            role=99,
            national_id='12345678901234'
        )
        admin.set_password('adminpass')
        db.session.add(admin)
        db.session.commit()
        add_log('SYSTEM_SETUP', 'Initial Super Admin account created.', admin.id)
def setup_database(app):
    with app.app_context():
        db.create_all()
        create_initial_data()
        print("Database setup complete.")
# ----------------------------------------------------
# 5. Statistics Functions
# ----------------------------------------------------
def get_student_attendance_stats(student_id):
    stats = {}
    student = User.query.get(student_id)
    if not student or not student.department_id:
        return stats
   
    records = AttendanceRecord.query.filter_by(student_id=student_id).all()
    present_sessions_ids = {r.session_id for r in records}
   
    all_sessions = Session.query.filter(
        Session.is_active == False,
        Session.creator.has(department_id=student.department_id)
    ).all()
   
    for session in all_sessions:
        creator_id = session.creator_id
       
        if creator_id not in stats:
            stats[creator_id] = {
                'doctor_name': session.creator.full_name,
                'present': 0,
                'absent': 0,
                'total_sessions': 0,
                'course_name': session.course_name
            }
       
        stats[creator_id]['total_sessions'] += 1
       
        if session.id in present_sessions_ids:
            stats[creator_id]['present'] += 1
        else:
            stats[creator_id]['absent'] += 1
           
    for record in records:
        if record.session_id not in {s.id for s in all_sessions}:
            creator_id = record.session.creator_id
            if creator_id not in stats:
                stats[creator_id] = {
                    'doctor_name': record.session.creator.full_name,
                    'present': 0,
                    'absent': 0,
                    'total_sessions': 0,
                    'course_name': record.session.course_name
                }
            stats[creator_id]['present'] += 1
            stats[creator_id]['total_sessions'] += 1
           
    return stats
# ----------------------------------------------------
# 6. Routes
# ----------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard_redirect'))
   
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
       
        user = User.query.filter_by(email=email).first()
       
        if user and user.check_password(password):
            if not user.is_active:
                flash('تم حظر حسابك. يرجى التواصل مع الإدارة.', 'danger')
                add_log('LOGIN_FAILED', f'Attempt to login by banned user {email}', user.id if user else None)
                return redirect(url_for('login'))
           
            login_user(user)
            flash(f'مرحباً بعودتك، {user.full_name}!', 'success')
            add_log('LOGIN_SUCCESS', f'User {user.email} logged in successfully.', user.id)
            return redirect(url_for('dashboard_redirect'))
        else:
            flash('البريد الإلكتروني أو كلمة المرور غير صحيحة.', 'danger')
            return redirect(url_for('login'))
           
    return render_template('auth/login.html')
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard_redirect'))
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
       
        national_id = request.form.get('national_id')
        age = request.form.get('age')
        year_id = request.form.get('year_id')
        department_id = request.form.get('department_id')
        section_id = request.form.get('section_id')
       
        action_source = request.form.get('action_source')
       
        if action_source == 'admin_panel':
            role = int(request.form.get('role', 1))
            if role not in [2, 3]:
                flash('دور غير مسموح.', 'danger')
                return redirect(url_for('super_admin_dash'))
        else:
            role = 1
       
        if password != confirm_password:
            flash('كلمتا المرور غير متطابقتين.', 'danger')
            return redirect(url_for('register'))
           
        if User.query.filter_by(email=email).first():
            flash('البريد الإلكتروني مسجل مسبقاً.', 'danger')
            return redirect(url_for('register'))
           
        if User.query.filter_by(national_id=national_id).first() and role == 1:
            flash('الرقم القومي مسجل مسبقاً.', 'danger')
            return redirect(url_for('register'))
       
        new_user = User(
            first_name=first_name,
            last_name=last_name,
            full_name=f'{first_name} {last_name}',
            email=email,
            national_id=national_id if role == 1 else None,
            age=int(age) if age and role == 1 else None,
            department_id=int(department_id) if department_id and role == 1 else None,
            year_id=int(year_id) if year_id and role == 1 else None,
            section_id=int(section_id) if section_id and role == 1 else None,
            role=role
        )
        new_user.set_password(password)
       
        db.session.add(new_user)
        db.session.commit()
       
        flash('تم إنشاء حسابك بنجاح! يرجى تسجيل الدخول.', 'success')
        add_log('USER_REGISTERED', f'User {new_user.email} registered (role {role}).', new_user.id)
        return redirect(url_for('login'))
    return render_template('auth/register.html', departments=Department.query.all(), years=AcademicYear.query.all(), sections=Section.query.all())
@app.route('/logout')
@login_required
def logout():
    add_log('LOGOUT', f'User {current_user.email} logged out.', current_user.id)
    logout_user()
    flash('تم تسجيل خروجك بنجاح.', 'info')
    return redirect(url_for('login'))
@app.route('/dashboard')
@login_required
def dashboard_redirect():
    if current_user.role == 99:
        return redirect(url_for('super_admin_dash'))
    elif current_user.role == 3:
        return redirect(url_for('doctor_dash'))
    elif current_user.role == 2:
        return redirect(url_for('assistant_dash'))
    else:
        return redirect(url_for('student_dash'))
# --- Dashboards ---
@app.route('/student')
@role_required(1)
def student_dash():
    # Filter sessions based on Student's Department and Section
    # Logic:
    # - Doctor's session: Show if student.dept == doctor.dept
    # - Assistant's session: Show if student.dept == assistant.dept AND student.section == session.section
   
    active_sessions = Session.query.filter_by(is_active=True).all()
    relevant_sessions = []
   
    for session in active_sessions:
        creator = session.creator
        if creator.role == 3: # Doctor
            if creator.department_id == current_user.department_id:
                relevant_sessions.append(session)
        elif creator.role == 2: # Assistant
            if creator.department_id == current_user.department_id and session.section_id == current_user.section_id:
                relevant_sessions.append(session)
   
    attendance_records = AttendanceRecord.query.filter_by(student_id=current_user.id).order_by(AttendanceRecord.attendance_time.desc()).all()
    attendance_stats = get_student_attendance_stats(current_user.id)
   
    # حساب إحصائيات الحضور لكل محاضر (دكتور/معيد) في نفس القسم فقط
    instructor_data = {}
   
    # أولاً: حساب عدد مرات الحضور
    for record in attendance_records:
        instructor = record.session.creator
        # التحقق من أن المحاضر في نفس القسم
        if instructor.department_id == current_user.department_id:
            instructor_name = instructor.full_name
            if instructor_name not in instructor_data:
                instructor_data[instructor_name] = {
                    'total_sessions': 0,
                    'attended': 0,
                    'role': 'دكتور' if instructor.role == 3 else 'معيد'
                }
            instructor_data[instructor_name]['attended'] += 1
   
    # ثانياً: حساب إجمالي الجلسات المنتهية التي يجب على الطالب حضورها
    ended_sessions = Session.query.filter_by(is_active=False).all()
    for session in ended_sessions:
        instructor = session.creator
        # التحقق من أن المحاضر في نفس القسم
        if instructor.department_id == current_user.department_id:
            # إذا كان دكتور: كل طلاب القسم يجب أن يحضروا
            # إذا كان معيد: فقط طلاب السكشن المحدد
            should_attend = False
            if instructor.role == 3: # دكتور
                should_attend = True
            elif instructor.role == 2: # معيد
                if session.section_id == current_user.section_id:
                    should_attend = True
           
            if should_attend:
                instructor_name = instructor.full_name
                if instructor_name not in instructor_data:
                    instructor_data[instructor_name] = {
                        'total_sessions': 0,
                        'attended': 0,
                        'role': 'دكتور' if instructor.role == 3 else 'معيد'
                    }
                instructor_data[instructor_name]['total_sessions'] += 1
   
    return render_template(
        'dashboard/student.html',
        active_sessions=relevant_sessions,
        attendance_records=attendance_records,
        attendance_stats=attendance_stats,
        instructor_data=instructor_data
    )
@app.route('/assistant')
@role_required(2)
def assistant_dash():
    sessions = Session.query.filter_by(creator_id=current_user.id).order_by(Session.start_time.desc()).all()
   
    active_sessions_list = Session.query.filter_by(creator_id=current_user.id, is_active=True).all()
   
    departments = Department.query.all()
    sections = Section.query.all()
   
    return render_template(
        'dashboard/assistant.html',
        sessions=sessions,
        active_sessions_list=active_sessions_list,
        departments=departments,
        sections=sections
    )
@app.route('/doctor')
@role_required(3)
def doctor_dash():
    sessions = Session.query.filter_by(creator_id=current_user.id).order_by(Session.start_time.desc()).all()
    active_sessions_list = Session.query.filter_by(creator_id=current_user.id, is_active=True).all()
   
    # Get sessions of assistants supervised by this doctor
    assistant_sessions = Session.query.join(User, Session.creator_id == User.id).filter(User.supervisor_id == current_user.id).order_by(Session.start_time.desc()).all()
   
    departments = Department.query.all()
    sections = Section.query.all()
    return render_template(
        'dashboard/doctor.html',
        sessions=sessions,
        assistant_sessions=assistant_sessions,
        active_sessions_list=active_sessions_list,
        departments=departments,
        sections=sections
    )
@app.route('/super_admin')
@role_required(99)
def super_admin_dash():
    students = User.query.filter_by(role=1).order_by(User.full_name).all()
    assistants = User.query.filter_by(role=2).order_by(User.full_name).all()
    doctors = User.query.filter_by(role=3).order_by(User.full_name).all()
   
    departments = Department.query.all()
    years = AcademicYear.query.all()
    sections = Section.query.all()
   
    return render_template(
        'dashboard/super_admin.html',
        students=students,
        assistants=assistants,
        doctors=doctors,
        departments=departments,
        years=years,
        sections=sections
    )
@app.route('/activity_logs')
@role_required(99)
def activity_logs():
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(100).all()
    return render_template('dashboard/admin_logs.html', logs=logs)
# --- Actions ---
@app.route('/record_attendance_geo', methods=['POST'])
@login_required
@role_required(1)
def record_attendance_geo():
    data = request.get_json()
    session_id = data.get('session_id')
    student_lat = float(data.get('lat'))
    student_lon = float(data.get('lon'))
    max_distance = float(data.get('max_distance', 500))
   
    session = Session.query.get(session_id)
    if not session or not session.is_active:
        return jsonify({'success': False, 'message': 'الجلسة غير نشطة أو غير موجودة.'})
       
    if AttendanceRecord.query.filter_by(student_id=current_user.id, session_id=session_id).first():
        return jsonify({'success': False, 'message': 'لقد سجلت حضورك بالفعل في هذه الجلسة.'})
    distance = calculate_distance(
        session.creator_latitude, session.creator_longitude,
        student_lat, student_lon
    )
    if distance <= max_distance:
        new_record = AttendanceRecord(
            student_id=current_user.id,
            session_id=session_id,
            is_manual=False,
            student_latitude=student_lat,
            student_longitude=student_lon,
            status='self'
        )
        db.session.add(new_record)
        db.session.commit()
       
        add_log('ATTENDANCE_SELF', f'Student {current_user.email} recorded self-attendance in session {session_id}.', current_user.id)
        return jsonify({'success': True, 'message': 'تم التسجيل بنجاح.'})
    else:
        message = f'أنت خارج النطاق المسموح به. المسافة: {distance:.2f} متر.'
        add_log('ATTENDANCE_FAILED', f'Student {current_user.email} failed GEO check for session {session_id}. Distance: {distance:.2f}m', current_user.id)
        return jsonify({'success': False, 'message': message})
@app.route('/start_session', methods=['POST'])
@login_required
def start_session():
    # Role check: 2 (Assistant) or 3 (Doctor)
    if current_user.role not in [2, 3]:
        flash('ليس لديك صلاحية بدء جلسة.', 'danger')
        return redirect(url_for('dashboard_redirect'))
    # Prevent multiple active sessions
    active_session = Session.query.filter_by(creator_id=current_user.id, is_active=True).first()
    if active_session:
        flash('لديك جلسة نشطة بالفعل. يرجى إنهاؤها قبل بدء جلسة جديدة.', 'warning')
        return redirect(url_for('dashboard_redirect'))
    max_distance_meters = request.form.get('max_distance_meters')
    creator_latitude = request.form.get('creator_latitude')
    creator_longitude = request.form.get('creator_longitude')
    section_id = request.form.get('section_id')
    if not all([max_distance_meters, creator_latitude, creator_longitude]):
        flash('يجب تحديد جميع بيانات الجلسة وتفعيل الموقع الجغرافي.', 'danger')
        return redirect(url_for('dashboard_redirect'))
    # Determine Course Name
    course_name = None
    if current_user.role == 3: # Doctor
        course_name = current_user.course_name
    elif current_user.role == 2: # Assistant
        if current_user.supervisor:
            course_name = current_user.supervisor.course_name
        else:
            course_name = "N/A"
    try:
        new_session = Session(
            course_name=course_name if course_name else "Unknown",
            creator_id=current_user.id,
            section_id=int(section_id) if section_id else None,
            creator_latitude=float(creator_latitude),
            creator_longitude=float(creator_longitude),
            max_distance_meters=float(max_distance_meters),
            is_active=True,
            start_time=datetime.utcnow()
        )
        db.session.add(new_session)
        db.session.commit()
       
        flash(f'تم بدء جلسة "{new_session.course_name}" بنجاح.', 'success')
        add_log('START_SESSION', f'User {current_user.email} started session {new_session.id}.', current_user.id)
    except Exception as e:
        flash(f'حدث خطأ أثناء بدء الجلسة: {e}', 'danger')
    return redirect(url_for('dashboard_redirect'))
@app.route('/end_session/<int:session_id>')
@login_required
def end_session(session_id):
    session = Session.query.get_or_404(session_id)
   
    if session.creator_id != current_user.id and current_user.role != 99:
        flash('ليس لديك صلاحية إنهاء هذه الجلسة.', 'danger')
        return redirect(url_for('dashboard_redirect'))
       
    if session.is_active:
        session.is_active = False
        session.end_time = datetime.utcnow()
        db.session.commit()
       
        flash(f'تم إنهاء جلسة "{session.course_name}" بنجاح.', 'success')
        add_log('END_SESSION', f'User {current_user.email} ended session {session.id}.', current_user.id)
   
    return redirect(url_for('dashboard_redirect'))
@app.route('/manual_attendance', methods=['POST'])
@login_required
def manual_attendance():
    if current_user.role not in [2, 3]:
        flash('ليس لديك صلاحية.', 'danger')
        return redirect(url_for('dashboard_redirect'))
    student_email = request.form.get('student_email')
   
    # Auto-select active session
    session = Session.query.filter_by(creator_id=current_user.id, is_active=True).first()
   
    if not session:
        flash('لا توجد جلسة نشطة حالياً لتسجيل الحضور فيها.', 'warning')
        return redirect(url_for('dashboard_redirect'))
   
    student = User.query.filter_by(email=student_email, role=1).first()
   
    if not student:
        flash(f'لا يوجد طالب مسجل بهذا البريد الإلكتروني: {student_email}.', 'danger')
        return redirect(url_for('dashboard_redirect'))
    if AttendanceRecord.query.filter_by(student_id=student.id, session_id=session.id).first():
        flash(f'الطالب {student.full_name} مسجل حضوره بالفعل في هذه الجلسة.', 'warning')
        return redirect(url_for('dashboard_redirect'))
    new_record = AttendanceRecord(
        student_id=student.id,
        session_id=session.id,
        is_manual=True,
        manual_by_id=current_user.id,
        attendance_time=datetime.utcnow(),
        status='manual'
    )
    db.session.add(new_record)
    db.session.commit()
   
    flash(f'تم تسجيل حضور الطالب {student.full_name} يدوياً بنجاح.', 'success')
    add_log('MANUAL_ATTENDANCE', f'User {current_user.email} recorded manual attendance for {student.email}.', current_user.id)
    return redirect(url_for('dashboard_redirect'))
@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    new_email = request.form.get('email')
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
   
    try:
        if new_email and new_email != current_user.email:
            if User.query.filter_by(email=new_email).first():
                flash('البريد الإلكتروني الجديد مسجل بالفعل.', 'danger')
                return redirect(url_for('dashboard_redirect'))
           
            current_user.email = new_email
            flash('تم تحديث البريد الإلكتروني بنجاح.', 'success')
        if new_password:
            if not current_user.check_password(current_password):
                flash('كلمة المرور الحالية غير صحيحة.', 'danger')
                return redirect(url_for('dashboard_redirect'))
           
            if new_password != confirm_password:
                flash('كلمتا المرور الجديدتان غير متطابقتين.', 'danger')
                return redirect(url_for('dashboard_redirect'))
               
            current_user.set_password(new_password)
            flash('تم تحديث كلمة المرور بنجاح.', 'success')
            add_log('PASSWORD_CHANGE', f'User {current_user.email} changed password.', current_user.id)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ في تحديث البيانات: {e}', 'danger')
       
    return redirect(url_for('dashboard_redirect'))
@app.route('/admin/create_user', methods=['POST'])
@login_required
@role_required(99)
def admin_create_user():
    try:
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = int(request.form.get('role', 3)) # Default to Doctor (3)
        department_id = request.form.get('department_id')
        course_name = request.form.get('course_name')
        if role != 3:
            flash('يمكن للمشرف إضافة حسابات الدكاترة فقط.', 'danger')
            return redirect(url_for('super_admin_dash'))
        if not all([first_name, last_name, email, password, confirm_password, department_id, course_name]):
            flash('يرجى ملء جميع الحقول المطلوبة.', 'danger')
            return redirect(url_for('super_admin_dash'))
           
        if password != confirm_password:
            flash('كلمة المرور غير متطابقة.', 'danger')
            return redirect(url_for('super_admin_dash'))
           
        if User.query.filter_by(email=email).first():
            flash('البريد الإلكتروني مسجل مسبقاً.', 'danger')
            return redirect(url_for('super_admin_dash'))
           
        new_user = User(
            first_name=first_name,
            last_name=last_name,
            full_name=f'{first_name} {last_name}',
            email=email,
            role=role,
            department_id=int(department_id),
            course_name=course_name,
            is_active=True
        )
        new_user.set_password(password)
       
        db.session.add(new_user)
        db.session.commit()
       
        flash('تم إنشاء حساب الدكتور بنجاح.', 'success')
        add_log('CREATE_USER', f'Created doctor {email}', current_user.id)
       
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء إنشاء الحساب: {str(e)}', 'danger')
        print(f"Error creating user: {e}")
       
    return redirect(url_for('super_admin_dash'))
@app.route('/doctor/add_assistant', methods=['POST'])
@login_required
@role_required(3)
def add_assistant():
    try:
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if not all([first_name, last_name, email, password, confirm_password]):
            flash('يرجى ملء جميع الحقول.', 'danger')
            return redirect(url_for('doctor_dash'))
        if password != confirm_password:
            flash('كلمة المرور غير متطابقة.', 'danger')
            return redirect(url_for('doctor_dash'))
        if User.query.filter_by(email=email).first():
            flash('البريد الإلكتروني مسجل مسبقاً.', 'danger')
            return redirect(url_for('doctor_dash'))
        new_user = User(
            first_name=first_name,
            last_name=last_name,
            full_name=f'{first_name} {last_name}',
            email=email,
            role=2, # Assistant
            department_id=current_user.department_id,
            supervisor_id=current_user.id,
            is_active=True
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('تم إضافة المعيد بنجاح.', 'success')
        add_log('CREATE_ASSISTANT', f'Doctor {current_user.email} created assistant {email}', current_user.id)
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ: {str(e)}', 'danger')
        print(f"Error creating assistant: {e}")
    return redirect(url_for('doctor_dash'))
@app.route('/admin/user/<int:user_id>/<action>')
@role_required(99)
def admin_user_action(user_id, action):
    user = User.query.get_or_404(user_id)
   
    if user.role == 99 and action != 'unban':
        flash('لا يمكن تنفيذ هذا الإجراء على حساب المشرف العام.', 'danger')
        return redirect(url_for('super_admin_dash'))
       
    log_msg = f'Admin {current_user.email} executed {action} action on user {user.email}.'
   
    if action == 'delete':
        db.session.delete(user)
        flash(f'تم حذف المستخدم {user.full_name} بنجاح.', 'success')
        db.session.commit()
        add_log('ADMIN_DELETE', log_msg, current_user.id)
    elif action == 'ban':
        user.is_active = False
        flash(f'تم حظر المستخدم {user.full_name} بنجاح.', 'warning')
        db.session.commit()
        add_log('ADMIN_BAN', log_msg, current_user.id)
    elif action == 'unban':
        user.is_active = True
        flash(f'تم فك حظر المستخدم {user.full_name} بنجاح.', 'success')
        db.session.commit()
        add_log('ADMIN_UNBAN', log_msg, current_user.id)
    else:
        flash('إجراء غير صالح.', 'danger')
    return redirect(url_for('super_admin_dash'))
@app.route('/admin/user/update/<int:user_id>', methods=['POST'])
@role_required(99)
def update_user_admin(user_id):
    user = User.query.get_or_404(user_id)
   
    user.first_name = request.form.get('first_name')
    user.last_name = request.form.get('last_name')
    user.full_name = f'{user.first_name} {user.last_name}'
    user.email = request.form.get('email')
    user.national_id = request.form.get('national_id')
   
    if user.role == 1:
        user.department_id = request.form.get('department_id', type=int)
        user.year_id = request.form.get('year_id', type=int)
        user.section_id = request.form.get('section_id', type=int)
    db.session.commit()
    flash(f'تم تحديث بيانات المستخدم {user.full_name} بنجاح.', 'success')
    add_log('ADMIN_EDIT_USER', f'Admin {current_user.email} updated user {user.email} details.', current_user.id)
    return redirect(url_for('super_admin_dash'))
def generate_excel_report(session_id):
    session = Session.query.get_or_404(session_id)
    records = AttendanceRecord.query.filter_by(session_id=session_id).all()
    data = []
    for record in records:
        status_text = 'يدوي' if record.is_manual else 'ذاتي'
       
        data.append({
            'التاريخ': record.timestamp.strftime('%Y-%m-%d') if hasattr(record, 'timestamp') else record.attendance_time.strftime('%Y-%m-%d'),
            'الوقت': record.timestamp.strftime('%H:%M:%S') if hasattr(record, 'timestamp') else record.attendance_time.strftime('%H:%M:%S'),
            'اسم الطالب': record.student.full_name,
            'القسم': record.student.department.name if record.student.department else 'N/A',
            'الفرقة': record.student.year.name if record.student.year else 'N/A',
            'السكشن': record.student.section.name if record.student.section else 'N/A',
            'الحالة': status_text
        })
   
    df = pd.DataFrame(data)
   
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Attendance Report')
       
    output.seek(0)
    return output
@app.route('/download_report/<int:session_id>')
@login_required
def download_report_route(session_id):
    # Check permissions: only creator, admin, or assistant of the course/section can download
    session = Session.query.get_or_404(session_id)
    if current_user.role != 99 and session.creator_id != current_user.id:
         # Add more granular checks if needed (e.g. assistant supervisor)
         pass
   
    output = generate_excel_report(session_id)
    return send_file(
        output,
        as_attachment=True,
        download_name=f'attendance_report_{session_id}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
@app.route('/report/student/<int:student_id>')
@login_required
@role_required(99)
def report_student_route(student_id):
    student = User.query.get_or_404(student_id)
    records = AttendanceRecord.query.filter_by(student_id=student.id).order_by(AttendanceRecord.attendance_time.desc()).all()
    return render_template('dashboard/admin_student_report.html', student=student, records=records)
@app.route('/my_report')
@login_required
@role_required(1)
def my_report_route():
    return my_report()
if __name__ == '__main__':
    setup_database(app)
    app.run(host='0.0.0.0', port=5000, debug=True)