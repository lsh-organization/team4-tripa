from django.db import models

# ==============================================
# 회원
# ==============================================

class Member(models.Model):
    m_id = models.AutoField(
        primary_key=True,
        db_column='M_ID'
        )
    user_id = models.CharField(
        max_length=30,
        db_column='ID'
        )
    pwd = models.CharField(
        max_length=30,
        db_column='PWD'
        )
    nickname = models.CharField(
        max_length=30,
        db_column='NICKNAME'
        )
    name = models.CharField(
        max_length=30,
        db_column='NAME'
        )

    class Meta:
        db_table = 'MEMBER'

    def __str__(self):
        return self.nickname

# ==============================================
# 여행
# ==============================================

class Travel(models.Model):
    t_id = models.AutoField(
        primary_key=True,
        db_column='T_ID'
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        db_column='M_ID'
    )
    t_day = models.DateField(
        null=True,
        blank=True,
        db_column='T_DAY'
    )
    t_place = models.CharField(
        max_length=100,
        db_column='T_PLACE'
    )
    t_title = models.CharField(
        max_length=100,
        db_column='T_TITLE'
    )
    t_way = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        db_column='T_WAY'
    )
    t_start = models.DateField(
        db_column='T_START'
    )
    t_end = models.DateField(
        db_column='T_END'
    )

    class Meta:
        db_table = 'TRAVEL'

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
    travel = models.ForeignKey(
        Travel,
        on_delete=models.CASCADE,
        db_column='T_ID'
    )

    class Meta:
        db_table = 'SCHEDULE'

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
        db_column='S_ID'
    )
    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        db_column='P_ID'
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
