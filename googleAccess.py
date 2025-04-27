import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

class GoogleDriveHandler:
    def __init__(self, service_account_path):
        self.service_account_path = service_account_path
        self.client = None

    def authenticate(self):
        self.scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_file(self.service_account_path, scopes=self.scopes)       
        self.client = gspread.authorize(credentials)

    def get_names_from_schedule(self, spreadsheet_id):
        spreadsheet = self.client.open_by_key(spreadsheet_id)
        sheet = spreadsheet.worksheet("Operator Availability vNew")
        names = []
        values = sheet.col_values(2)[10:]  # Start from row 11 (zero-indexed)
        for value in values:
            if value.strip().upper() == "YOUR NAME HERE":
                break
            if value.strip():
                names.append(value.strip())
        return names

    def get_log_sheet(self, spreadsheet_id):
        spreadsheet = self.client.open_by_key(spreadsheet_id)
        return spreadsheet.worksheet("log")

    def find_or_create_operator_log_row(self, spreadsheet_id, operator_name):
        sheet = self.get_log_sheet(spreadsheet_id)
        data = sheet.get_all_values()

        # Search for operator with missing clock out
        for idx, row in enumerate(data, start=1):
            if row and row[0] == operator_name and row[3] == "":
                return idx

        # Operator not found, append a new row
        sheet.append_row([operator_name] + [""] * 7)
        return len(data) + 1

    def update_operator_log(self, spreadsheet_id, operator_name, field, value):
        sheet = self.get_log_sheet(spreadsheet_id)
        col_map = {
            "operator": 1,
            "total_time": 2,
            "time_in": 3,
            "time_out": 4,
            "lunch_start": 5,
            "lunch_end": 6,
            "total_lunch": 7,
            "late": 8
        }
        row = self.find_or_create_operator_log_row(spreadsheet_id, operator_name)
        col = col_map[field]
        print(f"[DEBUG] Updating {operator_name} at row {row}, col {col} with value '{value}'")

        sheet.update_cell(row, col, value)

    def insert_shift_separator_if_needed(self, spreadsheet_id):
        sheet = self.get_log_sheet(spreadsheet_id)
        now = datetime.now()
        current_hour = now.hour

        data = sheet.get_all_values()
        last_shift_row = None
        for idx, row in enumerate(data):
            if any("Shift starting" in cell for cell in row):
                last_shift_row = idx

        if (current_hour in [6, 15]) and (last_shift_row is None or idx - last_shift_row > 2):
            shift_time = "7AM" if current_hour == 6 else "3PM"
            new_row = [f"=== Shift starting at {shift_time} ==="]
            sheet.insert_row(new_row, len(data) + 1)
            sheet.merge_cells(f"A{len(data)+1}:H{len(data)+1}")

    def calculate_total_time(self, time_in_str, time_out_str, lunch_start_str, lunch_end_str):
        fmt = "%H:%M:%S"
        time_in = datetime.strptime(time_in_str, fmt)
        time_out = datetime.strptime(time_out_str, fmt)
     

        total_time = time_out - time_in

        print(f"[DEBUG] Calculating total time:")
        print(f"  Time In: {time_in_str}")
        print(f"  Time Out: {time_out_str}")
        print(f"  Lunch Start: {lunch_start_str}")
        print(f"  Lunch End: {lunch_end_str}")

        if lunch_start_str and lunch_end_str:
            lunch_start = datetime.strptime(lunch_start_str, fmt)
            lunch_end = datetime.strptime(lunch_end_str, fmt)
            lunch_duration = lunch_end - lunch_start
            total_time -= lunch_duration
            return total_time, lunch_duration
        return total_time, None

    def calculate_late(self, time_in_str):
        fmt = "%H:%M:%S"
        time_in = datetime.strptime(time_in_str, fmt)
        if time_in.hour < 15:
            scheduled_time = time_in.replace(hour=7, minute=0, second=0)
        else:
            scheduled_time = time_in.replace(hour=15, minute=0, second=0)
        late = (time_in - scheduled_time).total_seconds() / 60
        return max(0, int(late))

    def save_clock_in(self, spreadsheet_id, operator_name, clock_in_time):
        self.insert_shift_separator_if_needed(spreadsheet_id)
        self.update_operator_log(spreadsheet_id, operator_name, "time_in", clock_in_time)

    def save_lunch_start(self, spreadsheet_id, operator_name, lunch_start_time):
        self.update_operator_log(spreadsheet_id, operator_name, "lunch_start", lunch_start_time)

    def save_lunch_end(self, spreadsheet_id, operator_name, lunch_end_time):
        self.update_operator_log(spreadsheet_id, operator_name, "lunch_end", lunch_end_time)

    def save_clock_out(self, spreadsheet_id, operator_name, clock_out_time):
        self.update_operator_log(spreadsheet_id, operator_name, "time_out", clock_out_time)

    def finalize_shift(self, spreadsheet_id, operator_name):
        sheet = self.get_log_sheet(spreadsheet_id)
        row = self.find_or_create_operator_log_row(spreadsheet_id, operator_name)
        time_in = sheet.cell(row, 3).value
        time_out = sheet.cell(row, 4).value
        lunch_start = sheet.cell(row, 5).value
        lunch_end = sheet.cell(row, 6).value

        if time_in and time_out:
            total_time, lunch_duration = self.calculate_total_time(time_in, time_out, lunch_start, lunch_end)
            late = self.calculate_late(time_in)
            self.update_operator_log(spreadsheet_id, operator_name, "total_time", str(total_time))
            self.update_operator_log(spreadsheet_id, operator_name, "late", late)
            print(f"[INFO] Finalized shift for {operator_name}")
        else:
            print(f"[WARNING] Incomplete shift, cannot finalize for {operator_name}")
