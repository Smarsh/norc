
import os
import re
import signal
import random
import time
from datetime import datetime, timedelta
from threading import Event

from django.db.models import (Model, Manager,
    BooleanField,
    CharField,
    DateTimeField)

from norc.core.models.schedules import Schedule, CronSchedule
from norc.core.constants import SCHEDULER_FREQUENCY, SCHEDULER_LIMIT
from norc.norc_utils import search
from norc.norc_utils.parallel import MultiTimer
from norc.norc_utils.log import make_log

class SchedulerManager(Manager):
    def undead(self):
        """Schedulers that are active but no recent heartbeat."""
        cutoff = datetime.utcnow() - \
            timedelta(seconds=(SCHEDULER_FREQUENCY * 1.5))
        return self.filter(active=True).filter(heartbeat__lt=cutoff)
    

class Scheduler(Model):
    """Scheduling process for handling Schedules.
    
    Takes unclaimed Schedules from the database and adds their next
    instance to a timer.  At the appropriate time, the instance is
    added to its queue and the Schedule is updated.
    
    Idea: Split this up into two threads, one which continuously handles
    already claimed schedules, the other which periodically polls the DB
    for new schedules.
    
    """
    objects = SchedulerManager()
    
    class Meta:
        app_label = 'core'
    
    # Whether the Scheduler is currently running.
    active = BooleanField(default=False)
    
    # The datetime of the Scheduler's last heartbeat.  Used in conjunction
    # with the active flag to determine whether a Scheduler is still alive.
    heartbeat = DateTimeField(null=True)
    
    # The host this scheduler ran on.
    host = CharField(default=lambda: os.uname()[1], max_length=128)
    
    def __init__(self, *args, **kwargs):
        Model.__init__(self, *args, **kwargs)
        self.flag = Event()
        
    def is_alive(self):
        """Whether the Scheduler is still running.
        
        A Scheduler is defined as alive if it is active and its last
        heartbeat was within the last N*SCHEDULER_FREQUENCY seconds,
        for some N > 1 (preferably with a decent amount of margin). 
        
        """
        return self.active and self.heartbeat > \
            datetime.utcnow() - timedelta(seconds=(SCHEDULER_FREQUENCY * 1.5))
    
    def start(self):
        """Starts the Scheduler."""
        if not hasattr(self, 'log'):
            self.log = make_log(self.log_path)
        if self.heartbeat != None:
            self.log.error("Cannot restart a scheduler.")
            return
        if __name__ == '__main__':
            for signum in [signal.SIGINT, signal.SIGTERM]:
                signal.signal(signum, lambda s, f: self.stop)
        self.timer = MultiTimer()
        self.active = True
        self.save()
        try:
            self.run()
        except:
            self.log.error('An unhandled exception occurred within ' +
                'the run function!', trace=True)
        self.timer.cancel()
        self.timer.join()
        Schedule.objects.filter(scheduler=self).update(scheduler=None)
        for t in self.timer.tasks:
            instance = t[2][1]
            print t
            instance.claimed = False
            instance.save()
    
    def run(self):
        while self.active:
            self.flag.clear()
            # Check for dead but active schedulers.
            Schedule.objects.orphaned().update(scheduler=None)
            CronSchedule.objects.orphaned().update(scheduler=None)
            undead = Scheduler.objects.undead()
            undead.update(active=False)
            # Beat heart.
            self.heartbeat = datetime.utcnow()
            self.save()
            unclaimed = Schedule.objects.unclaimed()[:SCHEDULER_LIMIT]
            for schedule in unclaimed:
                schedule.scheduler = self
                schedule.save()
                self.add(schedule)
            self.wait()
            self.active = Scheduler.objects.get(pk=self).active
    
    def wait(self):
        try:
            self.flag.wait(SCHEDULER_FREQUENCY)
        except KeyboardInterrupt:
            self.signal_handler(signal.SIGINT)
        except SystemExit:
            self.signal_handler(signal.SIGTERM)
    
    def stop(self):
        """Stops the Scheduler (passively)."""
        self.active = False
        self.save()
        self.flag.set()
    
    def add(self, schedule):
        """Adds the next instance for the schedule to the timer."""
        i = Instance.objects.create(source=schedule.task,
            start_date=schedule.next, schedule=schedule, claimed=True)
        self.timer.add_task(schedule.next, self.enqueue, [schedule, i])
    
    def enqueue(self, schedule, instance):
        """Called by the timer to add an instance to the queue.
        
        Try to make this method run AS QUICKLY AS POSSIBLE,
        otherwise tasks might start getting delayed if they
        are scheduled close together.
        
        """
        schedule.queue.push(instance)
        schedule.enqueued()
        if not schedule.finished():
            # self.flag.set()
            self.add(schedule)
        else:
            schedule.scheduler = None
        schedule.save()
    
    def signal_handler(self, signum, frame=None):
        """Handles signal interruption."""
        sig_name = None
        # A reverse lookup to find the signal name.
        for attr in dir(signal):
            if attr.startswith('SIG') and getattr(signal, attr) == signum:
                sig_name = attr
                break
        self.log.info("Signal '%s' received!" % sig_name)
        if signum == signal.SIGINT:
            self.stop()
        else:
            self.stop()
            # sys.exit(1)     # Maybe?
    
    def _get_log_path(self):
        return 'scheduler/scheduler-%s' % self.id
    log_path = property(_get_log_path)
    
    def __unicode__(self):
        return u"Scheduler #%s on host %s" % (self.id, self.host)
    
    __repr__ = __unicode__
    