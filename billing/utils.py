from datetime import timedelta

def get_previous_month_period(reference_data):
    first_day_this_month = reference_data.replace(day=1)
    last_day_previous_month = first_day_this_month - timedelta(day=1)
    first_day_previous_month = last_day_previous_month.replace(day=1)

    return first_day_previous_month, last_day_previous_month