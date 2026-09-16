from django.db import models

# ==============================================
# 회원
# ==============================================

class Member(models.Model):
    m_id = models.AutoField(primary_key=True, db_column='M_ID')
    email = models.EmailField(max_length=30,db_column='ID')
    pwd = models.CharField(max_length=30,db_column='PWD')
    nickname = models.CharField(max_length=30,db_column='NICKNAME')
    name = models.CharField(max_length=30,db_column='NAME')
    class Meta:
        db_table = 'member'
        managed = False

    def __str__(self):
        return self.nickname

# ==============================================
# 여행
# ==============================================

class Travel(models.Model):

    t_id = models.AutoField(primary_key=True,db_column='T_ID')
    member = models.ForeignKey(Member,on_delete=models.CASCADE,db_column='M_ID')
    t_day = models.DateField(db_column='T_DAY',null=True)
    t_place = models.CharField(max_length=100,db_column='T_PLACE',null=True)
    t_title = models.CharField(max_length=100,db_column='T_TITLE',null=True)
    t_way = models.CharField(max_length=30,db_column='T_WAY',null=True)
    t_start = models.DateField(db_column='T_START',null=True)
    t_end = models.DateField(db_column='T_END',null=True)
    class Meta:
        db_table = 'travel'
        managed = False

    def __str__(self):
        return self.t_title
     
# ==============================================
# 장소
# ==============================================

class Place(models.Model):
    p_id = models.AutoField(
        primary_key=True,
        db_column='P_ID'
    )
    travel = models.ForeignKey(
        Travel,
        on_delete=models.CASCADE,
        db_column='T_ID'
    )
    p_name = models.CharField(
        max_length=100,
        db_column='P_NAME'
    )
    p_addr = models.CharField(
        max_length=100,
        db_column='P_ADDR'
    )
    p_lat = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        db_column='P_LAT'
    )
    p_lon = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        db_column='P_LON'
    )
    p_kind = models.CharField(
        max_length=100,
        db_column='P_KIND'
    )
    p_image = models.URLField(
    max_length=500,
    null=True,
    blank=True,
    db_column='P_IMAGE'
    )

    class Meta:
        db_table = 'PLACE'
        
    def __str__(self):
        return self.p_name

# ==============================================
# 일정
# ==============================================

class Schedule(models.Model):
    s_id = models.AutoField(
        primary_key=True,
        db_column='S_ID'
    )
    s_day = models.DateField(
        db_column='S_DAY'
    )

    s_turn = models.IntegerField(
        db_column='S_TURN',
        null=True
    )
    travel = models.ForeignKey(
        Travel,
        on_delete=models.CASCADE,
        db_column='T_ID',
        related_name='schedules'
    )
    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        db_column='P_ID',
        related_name='schedules'
    )

    arrive_time = models.TimeField(
        null=True,
        blank=True,
        db_column='ARRIVE_TIME'
    )

    stay_time = models.IntegerField(
        null=True,
        blank=True,
        db_column='STAY_TIME'
    )

    start_time = models.TimeField(
        null=True,
        blank=True,
        db_column='START_TIME'
    )
    class Meta:
        db_table = 'schedule'

    def __str__(self):
        return str(self.s_day)
# ==============================================
# 일정 장소
# ==============================================

class SchedulePlace(models.Model):
    sp_id = models.AutoField(
        primary_key=True,
        db_column='SP_ID'
    )
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        db_column='S_ID',
        related_name='schedule_places'
    )
    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        db_column='P_ID',
        related_name='schedule_places'
    )
    visit_order = models.IntegerField(
        db_column='VISIT_ORDER'
    )

    stay_time = models.IntegerField(
        db_column='STAY_TIME',
        help_text="체류 시간(분)"
    )

    arrive_time = models.TimeField(
        db_column='ARRIVAL_TIME'
    )

    start_time = models.TimeField(
        db_column='START_TIME'
    )

    class Meta:
        db_table = 'SCHEDULE_PLACES'
        ordering = ['visit_order']

    @property
    def stay_time_display(self):
        if self.stay_time is None:
            return ''

        hours, minutes = divmod(self.stay_time, 60)

        if hours and minutes:
            return f'{hours}시간 {minutes}분'
        elif hours:
            return f'{hours}시간'
        else:
            return f'{minutes}분'

# ==============================================
# 카테고리
# ==============================================

class Category(models.Model):
    c_id = models.AutoField(
        primary_key=True,
        db_column='C_ID'
    )
    c_name = models.CharField(
        max_length=100,
        db_column='C_NAME'
    )

    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        db_column='P_ID'
        )

    class Meta:
        db_table = 'CATEGORIES'

    def __str__(self):
        return self.c_name

# ==============================================
# 비용
# ==============================================

class Pay(models.Model):
    pay_id = models.AutoField(
        primary_key=True,
        db_column='PAY_ID'
    )

    pay_context = models.CharField(
        max_length=100,
        db_column='PAY_CONTENT'
    )

    pay_pay = models.IntegerField(
        db_column='PAY_PAY'
    )

    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        db_column='S_ID'
    )

    class Meta:
        db_table = 'PAY'


class T_concept(models.Model):
    t_concept = models.CharField(
    max_length=200,
    db_column='T_CONCEPT',
    null=True
        )