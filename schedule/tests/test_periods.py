import datetime
import os

from django.test import TestCase
from django.conf import settings
from django.core.urlresolvers import reverse

from schedule.conf.settings import FIRST_DAY_OF_WEEK
from schedule.models import Event, Rule, Occurrence, Calendar
from schedule.periods import Period, Month, Week, Day, Year
from schedule.periods import OCCURRENCE_SPANS, OCCURRENCE_STARTS, OCCURRENCE_ENDS, OCCURRENCE_STARTS_ENDS
from schedule.utils import EventListManager

class TestPeriod(TestCase):

    def setUp(self):
        rule = Rule(frequency = "WEEKLY")
        rule.save()
        cal = Calendar(name="MyCal")
        cal.save()
        data = {
                'title': 'Recent Event',
                'start': datetime.datetime(2008, 1, 5, 8, 0),
                'end': datetime.datetime(2008, 1, 5, 9, 0),
                'end_recurring_period' : datetime.datetime(2008, 5, 5, 0, 0),
                'rule': rule,
                'calendar': cal
               }
        three_day_data = {
            'title': '3-Day Event',
            'start': datetime.datetime(2008, 1, 1, 8, 0),
            'end': datetime.datetime(2008, 1, 3, 9, 0),
            'end_recurring_period' : datetime.datetime(2008, 5, 5, 0, 0),
            'calendar': cal
            }
        recurring_event = Event(**data)
        recurring_event.save()
        self.recurring_event = recurring_event
        three_day_event = Event(**three_day_data)
        three_day_event.save()
        self.three_day_event = three_day_event
        self.period = Period(events=Event.objects.all(),
                            start = datetime.datetime(2008,1,4,7,0),
                            end = datetime.datetime(2008,1,21,7,0))
        self.week_period = Week(events=Event.objects.all(),
                                date=three_day_event.start)

    def test_get_occurrences(self):
        occurrence_list = self.period.occurrences
        self.assertEqual(["%s to %s" %(o.start, o.end) for o in occurrence_list],
            ['2008-01-05 08:00:00 to 2008-01-05 09:00:00',
             '2008-01-12 08:00:00 to 2008-01-12 09:00:00',
             '2008-01-19 08:00:00 to 2008-01-19 09:00:00'])

    def test_get_occurrence_partials(self):
        self._test_get_occurrence_partials(OCCURRENCE_STARTS_ENDS)

    def test_get_occurrence_partials_old(self):
        self._test_get_occurrence_partials(1, False)

    def _test_get_occurrence_partials(self, expected_class,
                                      using_new_occ_values=True):
        self.period.use_new_occurrence_class_values(using_new_occ_values)
        occurrence_dicts = self.period.get_occurrence_partials()
        self.assertEqual(
            [(occ_dict["class"],
            occ_dict["occurrence"].start,
            occ_dict["occurrence"].end)
            for occ_dict in occurrence_dicts],
            [
                (expected_class,
                 datetime.datetime(2008, 1, 5, 8, 0),
                 datetime.datetime(2008, 1, 5, 9, 0)),
                (expected_class,
                 datetime.datetime(2008, 1, 12, 8, 0),
                 datetime.datetime(2008, 1, 12, 9, 0)),
                (expected_class,
                 datetime.datetime(2008, 1, 19, 8, 0),
                 datetime.datetime(2008, 1, 19, 9, 0))
            ])

    def test_has_occurrence(self):
        self.assert_( self.period.has_occurrences() )
        slot = self.period.get_time_slot( datetime.datetime(2008,1,4,7,0),
                                          datetime.datetime(2008,1,4,7,12) )
        self.failIf( slot.has_occurrences() )

    def test_occurrence_classes(self):
        self.period.use_new_occurrence_class_values(True)
        self.week_period.use_new_occurrence_class_values(True)
        self.assert_( self.period.has_occurrences() )

        single_day_occ = self.period.get_occurrence_partials()[0]
        self.assertEqual(OCCURRENCE_STARTS_ENDS, single_day_occ["class"])

        week = self.week_period
        # week's events look like this:
        # Su Mu Tu We Th Fr Sa Su
        # -- -- e1 e1 e1 -- e2 --
        # (extra Sunday included to allow for fdow = 0 or 1)

        e1 = self.three_day_event
        e2 = self.recurring_event
        expected = [(None,None),
                    (None,None),
                    (e1,OCCURRENCE_STARTS),
                    (e1,OCCURRENCE_SPANS),
                    (e1,OCCURRENCE_ENDS),
                    (None,None),
                    (e2,OCCURRENCE_STARTS_ENDS),
                    ]
        if FIRST_DAY_OF_WEEK == 1:
            # just wrapping the empty sunday around if the fdow is monday
            expected = expected[1:] + expected[:1]
        for (expect, day) in zip(expected, week.get_days()):
            (expected_event, expected_occ_class) = expect
            expecting_occurrences = not expected_event is None
            self.assertEqual(expecting_occurrences, day.has_occurrences())
            if expecting_occurrences:
                occ = day.get_occurrence_partials()[0]
                self.assertEqual(expected_occ_class, occ['class'])
                self.assertEqual(expected_event, occ['occurrence'].event)

class TestYear(TestCase):

    def setUp(self):
        self.year = Year(events=[], date=datetime.datetime(2008,4,1))

    def test_get_months(self):
        months = self.year.get_months()
        self.assertEqual([month.start for month in months],
            [datetime.datetime(2008, i, 1) for i in range(1,13)])


class TestMonth(TestCase):

    def setUp(self):
        rule = Rule(frequency = "WEEKLY")
        rule.save()
        cal = Calendar(name="MyCal")
        cal.save()
        data = {
                'title': 'Recent Event',
                'start': datetime.datetime(2008, 1, 5, 8, 0),
                'end': datetime.datetime(2008, 1, 5, 9, 0),
                'end_recurring_period' : datetime.datetime(2008, 5, 5, 0, 0),
                'rule': rule,
                'calendar': cal
               }
        recurring_event = Event(**data)
        recurring_event.save()
        self.month = Month(events=Event.objects.all(),
                           date=datetime.datetime(2008, 2, 7, 9, 0))

    def test_get_weeks(self):
        weeks = self.month.get_weeks()
        actuals = [(week.start,week.end) for week in weeks]

        if FIRST_DAY_OF_WEEK == 0:
            expecteds = [
                (datetime.datetime(2008, 1, 27, 0, 0),
                 datetime.datetime(2008, 2, 3, 0, 0)),
                (datetime.datetime(2008, 2, 3, 0, 0),
                 datetime.datetime(2008, 2, 10, 0, 0)),
                (datetime.datetime(2008, 2, 10, 0, 0),
                 datetime.datetime(2008, 2, 17, 0, 0)),
                (datetime.datetime(2008, 2, 17, 0, 0),
                 datetime.datetime(2008, 2, 24, 0, 0)),
                (datetime.datetime(2008, 2, 24, 0, 0),
                 datetime.datetime(2008, 3, 2, 0, 0))
            ]
        else:
            expecteds = [
                (datetime.datetime(2008, 1, 28, 0, 0),
                 datetime.datetime(2008, 2, 4, 0, 0)),
                (datetime.datetime(2008, 2, 4, 0, 0),
                 datetime.datetime(2008, 2, 11, 0, 0)),
                (datetime.datetime(2008, 2, 11, 0, 0),
                 datetime.datetime(2008, 2, 18, 0, 0)),
                (datetime.datetime(2008, 2, 18, 0, 0),
                 datetime.datetime(2008, 2, 25, 0, 0)),
                (datetime.datetime(2008, 2, 25, 0, 0),
                 datetime.datetime(2008, 3, 3, 0, 0))
            ]

        for actual, expected in zip(actuals, expecteds):
            self.assertEqual(actual, expected)

    def test_get_days(self):
        weeks = self.month.get_weeks()
        week = list(weeks)[0]
        days = week.get_days()
        actuals = [(len(day.occurrences), day.start,day.end) for day in days]

        if FIRST_DAY_OF_WEEK == 0:
            expecteds = [
                (0, datetime.datetime(2008, 1, 27, 0, 0),
                 datetime.datetime(2008, 1, 28, 0, 0))
                (0, datetime.datetime(2008, 1, 28, 0, 0),
                 datetime.datetime(2008, 1, 29, 0, 0)),
                (0, datetime.datetime(2008, 1, 29, 0, 0),
                 datetime.datetime(2008, 1, 30, 0, 0)),
                (0, datetime.datetime(2008, 1, 30, 0, 0),
                 datetime.datetime(2008, 1, 31, 0, 0)),
                (0, datetime.datetime(2008, 1, 31, 0, 0),
                 datetime.datetime(2008, 2, 1, 0, 0)),
                (0, datetime.datetime(2008, 2, 1, 0, 0),
                 datetime.datetime(2008, 2, 2, 0, 0)),
                (1, datetime.datetime(2008, 2, 2, 0, 0),
                 datetime.datetime(2008, 2, 3, 0, 0)),
            ]

        else:
            expecteds = [
                (0, datetime.datetime(2008, 1, 28, 0, 0),
                 datetime.datetime(2008, 1, 29, 0, 0)),
                (0, datetime.datetime(2008, 1, 29, 0, 0),
                 datetime.datetime(2008, 1, 30, 0, 0)),
                (0, datetime.datetime(2008, 1, 30, 0, 0),
                 datetime.datetime(2008, 1, 31, 0, 0)),
                (0, datetime.datetime(2008, 1, 31, 0, 0),
                 datetime.datetime(2008, 2, 1, 0, 0)),
                (0, datetime.datetime(2008, 2, 1, 0, 0),
                 datetime.datetime(2008, 2, 2, 0, 0)),
                (1, datetime.datetime(2008, 2, 2, 0, 0),
                 datetime.datetime(2008, 2, 3, 0, 0)),
                (0, datetime.datetime(2008, 2, 3, 0, 0),
                 datetime.datetime(2008, 2, 4, 0, 0))
            ]

        for actual, expected in zip(actuals, expecteds):
            self.assertEqual(actual, expected)


    def test_month_convenience_functions(self):
        self.assertEqual( self.month.prev_month().start, datetime.datetime(2008, 1, 1, 0, 0))
        self.assertEqual( self.month.next_month().start, datetime.datetime(2008, 3, 1, 0, 0))
        self.assertEqual( self.month.current_year().start, datetime.datetime(2008, 1, 1, 0, 0))
        self.assertEqual( self.month.prev_year().start, datetime.datetime(2007, 1, 1, 0, 0))
        self.assertEqual( self.month.next_year().start, datetime.datetime(2009, 1, 1, 0, 0))


class TestDay(TestCase):
    def setUp(self):
        self.day = Day(events=Event.objects.all(),
                           date=datetime.datetime(2008, 2, 7, 9, 0))

    def test_day_setup(self):
        self.assertEqual( self.day.start, datetime.datetime(2008, 2, 7, 0, 0))
        self.assertEqual( self.day.end, datetime.datetime(2008, 2, 8, 0, 0))

    def test_day_convenience_functions(self):
        self.assertEqual( self.day.prev_day().start, datetime.datetime(2008, 2, 6, 0, 0))
        self.assertEqual( self.day.next_day().start, datetime.datetime(2008, 2, 8, 0, 0))

    def test_time_slot(self):
        slot_start = datetime.datetime(2008, 2, 7, 13, 30)
        slot_end = datetime.datetime(2008, 2, 7, 15, 0)
        period = self.day.get_time_slot( slot_start, slot_end )
        self.assertEqual( period.start, slot_start )
        self.assertEqual( period.end, slot_end )


class TestOccurrencePool(TestCase):

    def setUp(self):
        rule = Rule(frequency = "WEEKLY")
        rule.save()
        cal = Calendar(name="MyCal")
        cal.save()
        data = {
                'title': 'Recent Event',
                'start': datetime.datetime(2008, 1, 5, 8, 0),
                'end': datetime.datetime(2008, 1, 5, 9, 0),
                'end_recurring_period' : datetime.datetime(2008, 5, 5, 0, 0),
                'rule': rule,
                'calendar': cal
               }
        self.recurring_event = Event(**data)
        self.recurring_event.save()

    def testPeriodFromPool(self):
        """
            Test that period initiated with occurrence_pool returns the same occurrences as "straigh" period
            in a corner case whereby a period's start date is equal to the occurrence's end date
        """
        start = datetime.datetime(2008, 1, 5, 9, 0)
        end = datetime.datetime(2008, 1, 5, 10, 0)
        parent_period = Period(Event.objects.all(), start, end)
        period = Period(parent_period.events, start, end, parent_period.get_persisted_occurrences(), parent_period.occurrences)
        self.assertEquals(parent_period.occurrences, period.occurrences)

