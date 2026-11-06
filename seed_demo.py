"""Populate the database with demo voters and an election.

Usage:  python seed_demo.py
Creates 5 approved voters (password: Voter@1234), 1 pending voter, an open
election with 3 candidates, and a closed election with results.
"""
import os

from werkzeug.security import generate_password_hash

from backend.app import create_app
from backend.controllers import election_controller, vote_controller
from backend.extensions import db
from backend.models import Election, User

DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "Voter@1234")


def _voter(name, email, voter_id, status="approved"):
    user = User.query.filter_by(email=email).first()
    if user is None:
        user = User(full_name=name, email=email, voter_id=voter_id, role="voter",
                    status=status, password_hash=generate_password_hash(DEMO_PASSWORD))
        db.session.add(user)
        db.session.commit()
    return user


def main():
    """Seed demo data (idempotent for users; elections only if none exist)."""
    app = create_app()
    with app.app_context():
        admin = User.query.filter_by(role="admin").first()
        voters = [
            _voter("Ananya Rao", "ananya@college.edu", "1BY23IS101"),
            _voter("Rahul Verma", "rahul@college.edu", "1BY23IS102"),
            _voter("Sneha Kulkarni", "sneha@college.edu", "1BY23IS103"),
            _voter("Karthik Gowda", "karthik@college.edu", "1BY23IS104"),
            _voter("Meera Iyer", "meera@college.edu", "1BY23IS105"),
        ]
        _voter("Arjun Shetty", "arjun@college.edu", "1BY23IS106", status="pending")

        if Election.query.count() == 0:
            past = election_controller.create_election(
                {"title": "Class Representative 2026 - ISE 7A",
                 "description": "Election of the class representative for ISE 7th semester."},
                admin.id)
            ids = [election_controller.add_candidate(past.id, c, admin.id).id for c in (
                {"name": "Kavya Nair", "affiliation": "Independent"},
                {"name": "Rohan Das", "affiliation": "Tech Club"},
            )]
            election_controller.change_status(past.id, "open", admin.id)
            for voter, choice in zip(voters, [0, 1, 0, 0, 1]):
                vote_controller.cast_vote(voter, past.id, ids[choice])
            election_controller.change_status(past.id, "closed", admin.id)

            live = election_controller.create_election(
                {"title": "Student Council President 2026-27",
                 "description": "Annual election for the Student Council President. "
                                "One vote per verified student."}, admin.id)
            for cand in (
                {"name": "Aditi Sharma", "affiliation": "Progressive Students Forum",
                 "manifesto": "24x7 library access and a mentoring programme."},
                {"name": "Vikram Patil", "affiliation": "Campus Innovators",
                 "manifesto": "Startup incubation cell and hackathon funding."},
                {"name": "Nisha Reddy", "affiliation": "Independent",
                 "manifesto": "Better hostel facilities and transparent fee usage."},
            ):
                election_controller.add_candidate(live.id, cand, admin.id)
            election_controller.change_status(live.id, "open", admin.id)
        print("Demo data ready. Voter password:", DEMO_PASSWORD)


if __name__ == "__main__":
    main()
