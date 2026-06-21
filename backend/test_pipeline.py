from graph.build_graph import run_graph
from schemas.event_schema import IncomingEvent, EventType
from datetime import datetime

event = IncomingEvent(
    event_type=EventType.SMS,
    source_app='sms',
    redacted_text='GOVT HEALTH BENEFIT ALERT: Your senior citizen benefit of Rs 25000 has been approved. Enter your OTP at senior-health-pk.info to claim. Expires in 24 hours.',
    timestamp=datetime.utcnow(),
    user_id='test-user'
)
result = run_graph(event)
print('risk_flag:', result.risk_flag)
print('response_text:', result.response_text)
print('next_steps:', result.next_steps)
