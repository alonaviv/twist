from song_signup.models import TicketOrder, Customer

def update_customers():
    """
    Goes over all existing TicketOrders in the DB and creates or updates a Customer
    object for each logged in customer. Creates/updates a Customer object for the person who
    ordered the ticket as well, taking into account that he may or may not have logged in as well.

    If there are no logged in customers - creates/updates a singer Customer model for the person who made the order.
    """
    for ticket_order in TicketOrder.objects.all():
        if len(ticket_order.logged_in_customers) == ticket_order.customers.count() or (len(ticket_order.logged_in_customers) == 0 and ticket_order.customers.count() == 1):
            continue

        # TODO: Need a function that finds if a name already exists, using GPT
