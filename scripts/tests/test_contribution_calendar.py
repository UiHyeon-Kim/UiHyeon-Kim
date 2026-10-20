import copy
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from render_contribution_calendar import DataError, render, validate_days


class CalendarTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / 'data/contribution-calendar.json').read_text())

    def test_관측한_365일과_렌더의_모든_막대가_일치한다(self):
        svg = ET.fromstring(render(self.data))
        cells = [x for x in svg.iter() if 'data-date' in x.attrib]
        self.assertEqual(len(cells), 365)
        self.assertEqual([(x.attrib['data-date'], int(x.attrib['data-count']), int(x.attrib['data-level'])) for x in cells],
                         [(x['date'], x['count'], x['level']) for x in self.data['days']])
        self.assertEqual(sum(x.tag.endswith('polygon') for x in svg.iter()), 1095)

    def test_중복된_날짜는_수락하지_않는다(self):
        days = copy.deepcopy(self.data['days'])
        days[1]['date'] = days[0]['date']
        with self.assertRaises(DataError):
            validate_days(days, date.fromisoformat(self.data['to']))

    def test_하루가_누락되면_기존_두_출력_파일을_보존한다(self):
        broken = copy.deepcopy(self.data)
        broken['days'].pop()
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d/'broken.json').write_text(json.dumps(broken))
            for n in ('calendar.svg','data.json'):
                (d/n).write_text('prior-output')
            result = subprocess.run([sys.executable,str(ROOT/'scripts/render_contribution_calendar.py'),
                '--snapshot',str(d/'broken.json'),'--output',str(d/'calendar.svg'),
                '--data-output',str(d/'data.json')],capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((d/'calendar.svg').read_text(), 'prior-output')
            self.assertEqual((d/'data.json').read_text(), 'prior-output')

    def test_기여수와_색상_단계가_모순되면_수락하지_않는다(self):
        days = copy.deepcopy(self.data['days'])
        days[0]['count'] = 1
        days[0]['level'] = 0
        with self.assertRaises(DataError):
            validate_days(days, date.fromisoformat(self.data['to']))


if __name__ == '__main__':
    unittest.main()
