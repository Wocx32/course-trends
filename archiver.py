import datetime
import json
import sqlite3
import logging
import logging.config
import sys
import datetime
from requests import Session
from bs4 import BeautifulSoup
from db_setup import create_db
from rocketry import Rocketry
from rocketry.conds import every, time_of_month



logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': True,
})


fmt = '[%(asctime)s] [%(levelname)s] %(message)s'
date_fmt = '%d/%m/%Y:%H:%M:%S %z'
formatter = logging.Formatter(fmt, date_fmt)

logging.basicConfig(
	format=fmt,
	datefmt=date_fmt,
	level=logging.INFO,
	handlers=[
		logging.StreamHandler(sys.stdout)
	]
)

logger = logging.getLogger(__name__)


create_db()

conn = sqlite3.connect('db/seats.db')
conn.execute('pragma foreign_keys=ON')

curse = conn.cursor()

app = Rocketry(config={
    'timezone': datetime.timezone(datetime.timedelta(hours=5))
})


def course_soup(term):
    sess = Session()

    page = sess.get('https://mysis-fccollege.empower-xl.com/fusebox.cfm?fuseaction=CourseCatalog&rpt=1').content
    soup = BeautifulSoup(page, 'html.parser')
    data = soup.find('div',id='center_col').find_all('script')[1].get_text().replace('\r', '').replace('\n', '').replace(' ', '').split(';')
    jsonkey = data[0].replace('"', '').split('=')[1]
    utoken = data[1].replace('"', '').split('=')[1]



    params = {
        'fuseaction': 'CourseCatalog',
        'screen_width': '1920',
        'empower_global_term_id': term,
        'cs_descr': "",
        'empower_global_dept_id': '',
        'empower_global_course_id': '',
        'cs_sess_id': '',
        'cs_loca_id': '',
        'cs_inst_id': '',
        'cs_emph_id': '',
        'CS_time_start': '',
        'CS_time_end': '',
        'status': '1',
        utoken: jsonkey,
    }

    re = sess.post(f'https://mysis-fccollege.empower-xl.com/cfcs/courseCatalog.cfc?method=GetList&returnformat=json&', params=params)
    content = json.loads(re.content)['html']
    soup = BeautifulSoup(content, 'html.parser')
    return soup

def convert_time(time_string):
    return datetime.datetime.strptime(time_string, '%H:%M')

def get_data(content):
    return ' '.join(content.get_text().strip().replace('\t', '').replace('\n', '').split())


def parse_classroom(string):
    s = string.get_text().strip()

    if s[0] == 'S':
        return {'building': 'SBLOCK', 'classroom': s[6:]}

    if s[0] == 'E':
        return {'building': 'EBLOCK', 'classroom': s[6:]}

    if s[0] == 'L':
        return {'building': 'LUCAS', 'classroom': 'LUCAS'}

    if s == 'MCENTE01':
        return {'building': 'MCENTE', 'classroom': '01'}


def parse_schedule(string):
    s = string.split()
    
    time_from = s[-3]
    time_till = s[-1]

    days = s[1:-3]

    if len(days) == 1:
        days = list(days[0])

    start_time = convert_time(time_from)
    end_time = convert_time(time_till)

    if end_time < start_time:
        start_time, end_time = end_time, start_time

    return {'start_time': start_time, 'end_time': end_time, 'days': days}


def get_info(courses):

    data = []

    if 'No Courses' in courses.text:
        return data

    prev_course = None

    for j in courses.contents[5:-3:2]:


        if j and len(j.contents) >= 19 or len(j.contents) == 13:

            course = ' '.join(get_data(j.contents[3]).split(' ')[:3])

            data_dict = {
                "name": ' '.join(course.split(' ')[:2]),
                "section": course.split(' ')[-1]
            }

            if len(j.contents) == 19:
                available_seats = j.contents[15].get_text().strip()
                total_seats = j.contents[13].get_text().strip()

                data_dict.update({'available_seats': available_seats, 'total_seats': total_seats})

                data.append(data_dict)

            prev_course = course
        
        elif j and (len(j.contents) == 15 or len(j.contents) == 9):


            data_dict = {
                "name": ' '.join(prev_course.split(' ')[:2]),
                "section": prev_course.split(' ')[-1]
            }


            if len(j) == 15:
                available_seats = j.contents[11].get_text().strip()
                total_seats = j.contents[9].get_text().strip()
                data_dict.update({'available_seats': available_seats, 'total_seats': total_seats})

                data.append(data_dict)


    return data


def ingest(term, courses):
    for course in courses:
        course_code = course['name']
        course_section = course['section']
        total_seats = course['total_seats']
        available_seats = course['available_seats']

        try:
            curse.execute('INSERT INTO seat (term, course_code, course_section, available_seats) VALUES (?, ?, ?, ?)', (term, course_code, course_section, available_seats))
        except sqlite3.IntegrityError:
            logger.info(f'Course {course_code} {course_section} doesn\'t exist. Adding it to the course table.')
            curse.execute('INSERT INTO course VALUES (?, ?, ?, ?)', (term, course_code, course_section, total_seats))
            curse.execute('INSERT INTO seat (term, course_code, course_section, available_seats) VALUES (?, ?, ?, ?)', (term, course_code, course_section, available_seats))

    conn.commit()


@app.task(time_of_month.between(3, 28) & every('5 minutes'))
def ingest_terms():
    
    terms = ['2024FA', '2024SU']
    
    for term in terms:
        logger.info(f'Ingesting term {term}')
        sourp = course_soup(term)
        course_info = get_info(sourp)
        ingest(term, course_info)
        logger.info(f'Ingested term {term}')


if __name__ == '__main__':
    app.run()
