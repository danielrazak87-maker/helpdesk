from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit


def start_scheduler(app):
    scheduler = BackgroundScheduler()

    def sla_job():
        with app.app_context():
            from app.models.ticket import Ticket
            from app.services.sla_service import check_and_update_sla
            from app.services.escalation_service import run_escalation_checks
            from app.services.notification import send_notification

            open_tickets = Ticket.query.filter(
                Ticket.status.notin_(['resolved', 'closed'])
            ).all()

            for ticket in open_tickets:
                just_breached = check_and_update_sla(ticket)
                if just_breached and ticket.assigned_to:
                    send_notification(
                        user_id=ticket.assigned_to,
                        ticket_id=ticket.id,
                        title=f'🔴 SLA Breached: {ticket.ticket_number}',
                        message=f'The SLA for ticket "{ticket.title}" has been breached!',
                        ntype='danger'
                    )

            run_escalation_checks()

    scheduler.add_job(
        func=sla_job,
        trigger=IntervalTrigger(minutes=5),
        id='sla_check_job',
        name='SLA & Escalation Check',
        replace_existing=True
    )

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
