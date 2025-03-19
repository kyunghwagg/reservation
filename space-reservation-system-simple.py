# app.py - Flask 웹 애플리케이션 (로그인 기능 없음)

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///reservation.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 데이터베이스 모델
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    reservations = db.relationship('Reservation', backref='user', lazy=True)

class Space(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(200))
    reservations = db.relationship('Reservation', backref='space', lazy=True)

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    space_id = db.Column(db.Integer, db.ForeignKey('space.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 라우트 설정
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/enter_name', methods=['GET', 'POST'])
def enter_name():
    if request.method == 'POST':
        username = request.form.get('username')
        
        # 이름이 비어있는지 확인
        if not username:
            flash('이름을 입력해주세요')
            return redirect(url_for('enter_name'))
        
        # 사용자가 이미 존재하는지 확인
        user = User.query.filter_by(username=username).first()
        if not user:
            # 사용자 수가 9명을 초과하는지 확인
            user_count = User.query.count()
            if user_count >= 9:
                flash('최대 사용자 수(9명)에 도달했습니다')
                return redirect(url_for('enter_name'))
            
            # 새 사용자 생성
            user = User(username=username)
            db.session.add(user)
            db.session.commit()
        
        # 세션에 사용자 ID 저장
        session['user_id'] = user.id
        session['username'] = user.username
        
        return redirect(url_for('dashboard'))
    
    return render_template('enter_name.html')

@app.route('/exit')
def exit():
    # 세션에서 사용자 정보 제거
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    # 세션에 사용자 정보가 있는지 확인
    if 'user_id' not in session:
        flash('먼저 이름을 입력해주세요')
        return redirect(url_for('enter_name'))
    
    spaces = Space.query.all()
    return render_template('dashboard.html', username=session['username'], spaces=spaces)

@app.route('/calendar')
def calendar():
    # 세션에 사용자 정보가 있는지 확인
    if 'user_id' not in session:
        flash('먼저 이름을 입력해주세요')
        return redirect(url_for('enter_name'))
    
    # 모든 예약 정보를 가져옴
    reservations = Reservation.query.all()
    spaces = Space.query.all()
    
    # 달력에 표시할 데이터 준비
    calendar_data = []
    for reservation in reservations:
        user = User.query.get(reservation.user_id)
        space = Space.query.get(reservation.space_id)
        
        # ISO 형식의 날짜와 시간 문자열 생성
        start_datetime = datetime.combine(reservation.date, reservation.start_time)
        end_datetime = datetime.combine(reservation.date, reservation.end_time)
        
        calendar_data.append({
            'id': reservation.id,
            'title': f'{user.username} - {space.name}',
            'start': start_datetime.isoformat(),
            'end': end_datetime.isoformat()
        })
    
    return render_template('calendar.html', calendar_data=calendar_data, spaces=spaces)

@app.route('/make_reservation', methods=['GET', 'POST'])
def make_reservation():
    # 세션에 사용자 정보가 있는지 확인
    if 'user_id' not in session:
        flash('먼저 이름을 입력해주세요')
        return redirect(url_for('enter_name'))
    
    spaces = Space.query.all()
    
    if request.method == 'POST':
        space_id = request.form.get('space_id')
        date_str = request.form.get('date')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        
        # 문자열을 날짜와 시간 객체로 변환
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
        
        # 충돌 검사
        conflicting_reservations = Reservation.query.filter_by(date=date, space_id=space_id).all()
        for res in conflicting_reservations:
            if (start_time <= res.end_time and end_time >= res.start_time):
                flash('이미 예약된 시간입니다')
                return redirect(url_for('make_reservation'))
        
        # 새 예약 생성
        new_reservation = Reservation(
            date=date,
            start_time=start_time,
            end_time=end_time,
            user_id=session['user_id'],
            space_id=space_id
        )
        
        db.session.add(new_reservation)
        db.session.commit()
        
        flash('예약이 성공적으로 생성되었습니다')
        return redirect(url_for('calendar'))
    
    return render_template('make_reservation.html', spaces=spaces)

@app.route('/my_reservations')
def my_reservations():
    # 세션에 사용자 정보가 있는지 확인
    if 'user_id' not in session:
        flash('먼저 이름을 입력해주세요')
        return redirect(url_for('enter_name'))
    
    reservations = Reservation.query.filter_by(user_id=session['user_id']).all()
    return render_template('my_reservations.html', reservations=reservations)

@app.route('/cancel_reservation/<int:id>')
def cancel_reservation(id):
    # 세션에 사용자 정보가 있는지 확인
    if 'user_id' not in session:
        flash('먼저 이름을 입력해주세요')
        return redirect(url_for('enter_name'))
    
    reservation = Reservation.query.get_or_404(id)
    
    # 예약이 현재 사용자의 것인지 확인
    if reservation.user_id != session['user_id']:
        flash('자신의 예약만 취소할 수 있습니다')
        return redirect(url_for('my_reservations'))
    
    db.session.delete(reservation)
    db.session.commit()
    
    flash('예약이 취소되었습니다')
    return redirect(url_for('my_reservations'))

# 초기화 함수
def initialize_app():
    with app.app_context():
        db.create_all()
        
        # 공간이 없으면 기본 공간 생성
        if Space.query.count() == 0:
            space1 = Space(name='공간 1', description='첫 번째 공간')
            space2 = Space(name='공간 2', description='두 번째 공간')
            
            db.session.add(space1)
            db.session.add(space2)
            db.session.commit()

if __name__ == '__main__':
    initialize_app()
    app.run(debug=True)
