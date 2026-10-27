from django.db import models


# ==============================================
# 회원
# ==============================================

class Member(models.Model):

    m_id = models.AutoField(
        primary_key=True,
        db_column='M_ID'
    )

    email = models.EmailField(
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
        db_table = 'member'
        managed = False

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
        db_column='M_ID',
        related_name='travels'
    )

    # 기존 필드
    t_day = models.DateField(
        db_column='T_DAY',
        null=True,
        blank=True
    )

    t_place = models.CharField(
        max_length=100,
        db_column='T_PLACE',
        null=True,
        blank=True
    )

    t_title = models.CharField(
        max_length=100,
        db_column='T_TITLE',
        null=True,
        blank=True
    )

    t_way = models.CharField(
        max_length=30,
        db_column='T_WAY',
        null=True,
        blank=True
    )

    t_start = models.DateField(
        db_column='T_START',
        null=True,
        blank=True
    )

    t_end = models.DateField(
        db_column='T_END',
        null=True,
        blank=True
    )

    # ==========================================
    # 총 예산
    # ==========================================

    t_budget = models.IntegerField(
        db_column='T_BUDGET',
        default=100000
    )

    # ==========================================
    # 자동 일정 추천에 필요한 추가 정보
    # ==========================================

    # 사용자의 출발 장소
    start_place = models.CharField(
        max_length=200,
        db_column='START_PLACE',
        null=True,
        blank=True
    )

    start_addr = models.CharField(
        max_length=255,
        db_column='START_ADDR',
        null=True,
        blank=True
    )

    start_lat = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        db_column='START_LAT',
        null=True,
        blank=True
    )

    start_lon = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        db_column='START_LON',
        null=True,
        blank=True
    )

    start_time = models.TimeField(
        db_column='START_TIME',
        null=True,
        blank=True
    )

    # 숙소
    accommodation = models.CharField(
        max_length=200,
        db_column='ACCOMMODATION',
        null=True,
        blank=True
    )

    accommodation_lat = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        db_column='ACCOMMODATION_LAT',
        null=True,
        blank=True
    )

    accommodation_lon = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        db_column='ACCOMMODATION_LON',
        null=True,
        blank=True
    )

    # 체크인 시간
    checkin_time = models.TimeField(
        db_column='CHECKIN_TIME',
        null=True,
        blank=True
    )

    # 마지막 DAY 최초 출발지 복귀 예정 시간
    # 값이 없으면 화면/경로 API에서 22:00을 기본값으로 사용한다.
    return_time = models.TimeField(
        db_column='RETURN_TIME',
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'travel'
        managed = False

    def __str__(self):
        return self.t_title or ''


# ==============================================
# 여행 날짜별 계획
# ==============================================

class TravelDayPlan(models.Model):

    tdp_id = models.AutoField(
        primary_key=True,
        db_column='TDP_ID'
    )

    travel = models.ForeignKey(
        Travel,
        on_delete=models.CASCADE,
        db_column='T_ID',
        related_name='day_plans'
    )

    plan_date = models.DateField(
        db_column='PLAN_DATE'
    )

    accommodation_name = models.CharField(
        max_length=200,
        db_column='ACCOMMODATION_NAME',
        null=True,
        blank=True
    )

    accommodation_addr = models.CharField(
        max_length=255,
        db_column='ACCOMMODATION_ADDR',
        null=True,
        blank=True
    )

    accommodation_lat = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        db_column='ACCOMMODATION_LAT',
        null=True,
        blank=True
    )

    accommodation_lon = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        db_column='ACCOMMODATION_LON',
        null=True,
        blank=True
    )

    arrival_time = models.TimeField(
        db_column='ARRIVAL_TIME',
        null=True,
        blank=True
    )

    departure_time = models.TimeField(
        db_column='DEPARTURE_TIME',
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'travel_day_plan'
        managed = False
        ordering = ['plan_date']

        constraints = [
            models.UniqueConstraint(
                fields=['travel', 'plan_date'],
                name='unique_travel_day_plan'
            )
        ]

    def __str__(self):
        return f'{self.travel} - {self.plan_date}'


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
        db_column='C_NAME',
        unique=True
    )

    class Meta:
        db_table = 'CATEGORIES'

    def __str__(self):
        return self.c_name


# ==============================================
# 여행 - 카테고리 연결
# ==============================================

class TravelCategory(models.Model):

    tc_id = models.AutoField(
        primary_key=True,
        db_column='TC_ID'
    )

    travel = models.ForeignKey(
        Travel,
        on_delete=models.CASCADE,
        db_column='T_ID',
        related_name='travel_categories'
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        db_column='C_ID',
        related_name='travel_categories'
    )

    class Meta:
        db_table = 'TRAVEL_CATEGORY'

        constraints = [
            models.UniqueConstraint(
                fields=['travel', 'category'],
                name='unique_travel_category'
            )
        ]

    def __str__(self):
        return f'{self.travel} - {self.category}'


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
        db_column='T_ID',
        related_name='places'
    )

    p_name = models.CharField(
        max_length=100,
        db_column='P_NAME'
    )

    p_addr = models.CharField(
        max_length=200,
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

    # 실제 장소 종류
    # 예: 역사 / 카페 / 음식 / 공원
    p_kind = models.CharField(
        max_length=100,
        db_column='P_KIND',
        null=True,
        blank=True
    )

    p_image = models.CharField(
        max_length=500,
        db_column='P_IMAGE',
        null=True,
        blank=True
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
        db_column='T_ID',
        related_name='schedules'
    )

    class Meta:
        db_table = 'SCHEDULE'
        ordering = ['s_day']

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

    # 몇 번째 방문 장소인지
    visit_order = models.IntegerField(
        db_column='VISIT_ORDER'
    )

    # 체류 시간 (분)
    stay_time = models.IntegerField(
        db_column='STAY_TIME',
        null=True,
        blank=True,
        help_text='체류 시간(분)'
    )

    # 도착 시간
    arrive_time = models.TimeField(
        db_column='ARRIVAL_TIME',
        null=True,
        blank=True
    )

    # 출발 시간
    start_time = models.TimeField(
        db_column='START_TIME',
        null=True,
        blank=True
    )

    # 이전 장소 → 현재 장소 이동 시간
    travel_time = models.IntegerField(
        db_column='TRAVEL_TIME',
        null=True,
        blank=True,
        help_text='이동 시간(분)'
    )

    class Meta:
        db_table = 'SCHEDULE_PLACES'
        ordering = ['visit_order']

        constraints = [
            models.UniqueConstraint(
                fields=['schedule', 'visit_order'],
                name='unique_schedule_visit_order'
            )
        ]

    def __str__(self):
        return (
            f'{self.schedule.s_day}'
            f' - {self.visit_order}. '
            f'{self.place.p_name}'
        )

    @property
    def stay_time_display(self):

        if self.stay_time is None:
            return ''

        hours, minutes = divmod(
            self.stay_time,
            60
        )

        if hours and minutes:
            return f'{hours}시간 {minutes}분'

        elif hours:
            return f'{hours}시간'

        return f'{minutes}분'


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
        db_column='PAY_CONTENT',
        null=True,
        blank=True
    )

    pay_pay = models.IntegerField(
        db_column='PAY_PAY',
        null=True,
        blank=True
    )

    # 어느 날짜의 비용인지
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        db_column='S_ID',
        null=True,
        blank=True,
        related_name='payments'
    )

    # 어느 장소에서 발생한 비용인지
    # 장소와 관계없는 비용은 NULL 가능
    place = models.ForeignKey(
        Place,
        on_delete=models.SET_NULL,
        db_column='P_ID',
        null=True,
        blank=True,
        related_name='payments'
    )

    class Meta:
        db_table = 'PAY'

    def __str__(self):

        if self.pay_context:
            return f'{self.pay_context} - {self.pay_pay or 0}원'

        return f'{self.pay_pay or 0}원'