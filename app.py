# app.py
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.contrib.github import make_github_blueprint, github
import logging
from model import db, User, Course, reset_database  # استدعاء الكائنات من model.py

app = Flask(__name__)
app.secret_key = 'your_secret_key'
login_manager = LoginManager()
login_manager.init_app(app)

# إعداد قاعدة البيانات
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# إعداد تسجيل العمليات
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

with app.app_context():
    reset_database()

# إعداد Google OAuth
google_bp = make_google_blueprint(client_id='YOUR_GOOGLE_CLIENT_ID', client_secret='YOUR_GOOGLE_CLIENT_SECRET', redirect_to='google_login')
app.register_blueprint(google_bp, url_prefix='/google_login')

# إعداد GitHub OAuth
github_bp = make_github_blueprint(client_id='YOUR_GITHUB_CLIENT_ID', client_secret='YOUR_GITHUB_CLIENT_SECRET', redirect_to='github_login')
app.register_blueprint(github_bp, url_prefix='/github_login')

# تحميل المستخدم
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# الصفحة الرئيسية
@app.route('/')
def home():
    all_courses = Course.query.all()  # استرجاع جميع الدورات
    logging.info(f'Total courses retrieved: {len(all_courses)}')
    
    # إنشاء مجموعة لتخزين أنواع الدورات الفريدة
    unique_course_types = set(course.course_type for course in all_courses)
    
    # تنظيم الدورات حسب النوع
    courses_by_type = {}
    for course in all_courses:
        if course.course_type not in courses_by_type:
            courses_by_type[course.course_type] = []
        courses_by_type[course.course_type].append(course)
    
    # الحصول على اسم المستخدم الحالي إذا كان مسجلاً الدخول
    username = current_user.username if current_user.is_authenticated else 'زائر'
    
    # تمرير البيانات إلى القالب
    return render_template('user/index.html', username=username, courses_by_type=courses_by_type, unique_course_types=unique_course_types)

# صفحة "About"
@app.route('/user/about')
def about():
    return render_template('user/about.html')

@app.route('/admin/index')
def admin():
    return render_template('admin/index.html')

# صفحة تسجيل الدخول
@app.route('/user/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            logging.info(f'User {username} logged in successfully.')
            return redirect(url_for('home'))
        else:
            logging.warning(f'Failed login attempt for username: {username}')
            flash('اسم المستخدم أو كلمة المرور غير صحيحة')
            return redirect(url_for('login'))

    return render_template('user/login.html')



@app.route('/user/login_pass', methods=['GET', 'POST'])
def login_pass():
    return render_template('user/login_pass.html')


@app.route('/user/profile')
@login_required  # تأكد من أن المستخدم مسجل الدخول
def profile():
    # الحصول على بيانات المستخدم الحالي
    user_data = {
        'username': current_user.username,
        'email': current_user.email,
        'join_date': current_user.created_at,  # افترض أن لديك حقل join_date في نموذج User
       'likes_count': current_user.likes_count,
       'shares_count': current_user.shares_count,

    }
    
    # تمرير البيانات إلى القالب
    return render_template('user/profileuserr.html', user_data=user_data)

# صفحة التسجيل
@app.route('/user/register', methods=['GET', 'POST'])
def register():
    message = None
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            message = 'كلمة المرور وتأكيد كلمة المرور غير متطابقتين'
            return render_template('user/register.html', message=message)

        if User.query.filter_by(username=username).first():
            message = 'اسم المستخدم موجود بالفعل'
            return render_template('user/register.html', message=message)

        if User.query.filter_by(email=email).first():
            message = 'البريد الإلكتروني موجود بالفعل'
            return render_template('user/register.html', message=message)

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password, email=email)
        db.session.add(new_user)
        db.session.commit()

        logging.info(f'New user registered: {username}')
        return redirect(url_for('login'))

    return render_template('user/register.html', message=message)

@app.route('/admin/add_course', methods=['GET', 'POST'])
def add_course():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        image_url = request.form['image_url']
        course_type = request.form['course_type']

        new_course = Course(title=title, description=description, image_url=image_url, course_type=course_type)
        db.session.add(new_course)  
        db.session.commit()  

        logging.info(f'New course added: {title}')
        return redirect(url_for('admin_courses'))  # إعادة التوجيه إلى صفحة الكورسات
    
    return render_template('admin/add_course.html')

@app.route('/admin/users')
def users():
    all_users = User.query.all()
    current_user_count = User.query.count()
    
    # جمع بيانات تاريخ التسجيل لكل مستخدم
    daily_counts = {}
    monthly_counts = {}
    yearly_counts = {}

    for user in all_users:
        date = user.created_at.date()  # استخدم التاريخ فقط
        month = user.created_at.strftime("%Y-%m")  # صيغة السنة-الشهر
        year = user.created_at.year  # السنة

        # عد المستخدمين حسب اليوم
        if date in daily_counts:
            daily_counts[date] += 1
        else:
            daily_counts[date] = 1

        # عد المستخدمين حسب الشهر
        if month in monthly_counts:
            monthly_counts[month] += 1
        else:
            monthly_counts[month] = 1

        # عد المستخدمين حسب السنة
        if year in yearly_counts:
            yearly_counts[year] += 1
        else:
            yearly_counts[year] = 1

    # تحويل البيانات إلى قوائم لتسهيل استخدامها في الرسوم البيانية
    daily_labels = list(daily_counts.keys())
    daily_values = list(daily_counts.values())

    monthly_labels = list(monthly_counts.keys())
    monthly_values = list(monthly_counts.values())

    yearly_labels = list(yearly_counts.keys())
    yearly_values = list(yearly_counts.values())

    return render_template('admin/users.html', users=all_users, current_user_count=current_user_count, 
                           daily_labels=daily_labels, daily_values=daily_values,
                           monthly_labels=monthly_labels, monthly_values=monthly_values,
                           yearly_labels=yearly_labels, yearly_values=yearly_values)
@app.route('/admin/users/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    user = User.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
        logging.info(f'User {user.username} deleted successfully.')
        return redirect(url_for('users')) 
    else:
        logging.warning(f'Tried to delete a non-existing user with ID: {user_id}.')
        return redirect(url_for('users')) 

# صفحة تسجيل الدخول عبر Google
@app.route('/google_login')
def google_login():
    if not google.authorized:
        return redirect(url_for('google.login'))
    resp = google.get('/plus/v1/people/me')
    assert resp.ok, resp.text
    return f'Welcome, {resp.json()["displayName"]}!'

# صفحة تسجيل الدخول عبر GitHub
@app.route('/github_login')
def github_login():
    if not github.authorized:
        return redirect(url_for('github.login'))
    resp = github.get('/user')
    assert resp.ok, resp.text
    return f'Welcome, {resp.json()["login"]}!'

# تسجيل الخروج
@app.route('/user/logout')
@login_required
def logout():
    username = current_user.username
    logout_user()
    logging.info(f'User {username} logged out successfully.')
    return redirect(url_for('home'))

# عرض الدورات
@app.route('/admin/admin_courses')
def admin_courses():
    all_courses = Course.query.all()
    return render_template('admin/admin_courses.html', courses=all_courses)


@app.route('/user/courses')
@login_required
def user_courses():
    all_courses = Course.query.all()
    logging.info(f'Total courses retrieved: {len(all_courses)}')  # سجّل عدد الدورات المسترجعة
    courses_by_type = {}

    for course in all_courses:
        if course.course_type not in courses_by_type:
            courses_by_type[course.course_type] = []
        courses_by_type[course.course_type].append(course)

    return render_template('user/courses.html', courses_by_type=courses_by_type)


@app.route('/like/<int:course_id>', methods=['POST'])
def like_course(course_id):
    course = Course.query.get(course_id)
    if course:
        course.likes += 1  # زيادة عدد الإعجابات للدورة
        current_user.likes_count += 1  # زيادة عدد الإعجابات للمستخدم
        db.session.commit()  # حفظ التغييرات في قاعدة البيانات
        return jsonify(success=True)
    return jsonify(success=False), 404


@app.route('/admin/admin_courses/<int:course_id>', methods=['POST'])
def delete_course(course_id):
    course = Course.query.get(course_id)
    if course:
        db.session.delete(course)
        db.session.commit()
        logging.info(f'Course {course.title} deleted successfully.')
        return redirect(url_for('admin_courses'))
    else:
        logging.warning(f'Tried to delete a non-existing course with ID: {course_id}.')
        return redirect(url_for('admin_courses'))

if __name__ == '__main__':
    app.run(debug=True)