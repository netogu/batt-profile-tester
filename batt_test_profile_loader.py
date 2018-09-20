import csv
import time
import os

class profile_state_machine():
    """ Run through profile defined in CSV file."""

    def __init__(self, csv_reader):
        self.reader = csv_reader
        self.row = next(csv_reader)
        self.new_step = 1
        self.parse_row()

    def get_number_of_steps(self):
        row_list = []
        for row in self.reader:
            row_list += row['step']
        self.no_profile_steps = max(row_list)
        return self.no_profile_steps

    def next_step(self):
        self.row = next(self.reader)
        self.parse_row()
        self.new_step = 1

    def parse_row(self):

        self.step = int(self.row['step'])
        self.vsp = float(self.row['Vsp'])
        self.ilim_pos = float(self.row['Ilim_pos'])
        self.ilim_neg = float(self.row['Ilim_neg'])
        self.command = self.row['command']
        self.value = float(self.row['value'])
        self.message = self.row['message']

    def run_profile(self, battery):

        if(self.command == 'timeout'):
            return self.timeout_event()
        if(self.command == 'end_current'):
            return self.end_current_event(battery)
        if(self.command == 'output_state'):
            return self.output_state_event()
        if(self.command == 'float_voltage'):
            return self.float_voltage_event(battery)

    def set_event_function(self, func):
        self.event_func = func

    def get_step_params(self, output_state = 'NA'):
        return {'voltage': self.vsp,'ilim_pos': self.ilim_pos, 'ilim_neg': self.ilim_neg, 'output_state': output_state}

    def print_current_param(self, output_state = 'NA'):
        print('step = {} | voltage = {}V / +ilim = {}A / -ilim = {}A / output state = {} : {}'.format(self.step, self.vsp, self.ilim_pos, self.ilim_neg, output_state,self.message))

    def timeout_event(self):

        if(self.new_step == 1):

            self.print_current_param(self.output_status)
            self.event_func(**self.get_step_params())
            self.timer_start = time.time()
            self.new_step = 0

        if(self.new_step == 0):
            # Read time and trigger a step change when condition is met
            self.current_time = time.time() - self.timer_start
            if(self.current_time > self.value):
                print("Timeout condition met...")
                self.next_step()

    def end_current_event(self, battery):

        if(self.new_step == 1):

            self.print_current_param(self.output_status)
            self.event_func(**self.get_step_params())
            self.new_step = 0

        if(self.new_step == 0):
            if(battery.current < self.value):
                print("{} < {} :End Current condition met...".format(battery.current,self.value))
                self.next_step()

    def float_voltage_event(self, battery):

        if(self.new_step == 1):

            self.print_current_param(self.output_status)
            self.event_func(**self.get_step_params())
            self.new_step = 0

        if(self.new_step == 0):
            if(battery.voltage >= self.value):
                print("Float Voltage condition met...")
                self.next_step()

    def output_state_event(self):

            if(self.new_step == 1):
                if(self.value == 1):
                    self.output_status = 'ON'
                    self.print_current_param('ON')
                    self.event_func(**self.get_step_params(output_state ='ON'))
                if(self.value == 0):
                    self.output_status = 'OFF'
                    self.print_current_param('OFF')
                    self.event_func(**self.get_step_params(output_state = 'OFF'))
                self.new_step = 0

            if(self.new_step == 0):

                print("Charger Output State changed...")
                self.next_step()




if __name__ == '__main__':

    class battery():
        voltage = 13.8
        current = 10.2

    def timer_func_test(battery):
        print('Result = {}, {}'.format(battery.voltage, battery.current))

    def change_param_test(voltage=0, ilim_pos=0, ilim_neg=0, output_state='OFF'):
        print('voltage = {} ilim+ = {} ilim- = {} output state = {}'.format(voltage,ilim_pos,ilim_neg,output_state))


    local_path =  os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(local_path, 'profile.csv')

    batt = battery()

    with open(filename) as file:
        csv_reader = csv.DictReader(file)
        profile_reader = profile_state_machine(csv_reader)
        profile_reader.set_event_function(change_param_test)
        print(profile_reader.get_number_of_steps())
        while(1):
            #profile_reader.run_profile(batt)
            time.sleep(1)
