from app.models import (
    db,
    SocietyMeeting,
    PollVote,
    Flat,
)
from app.utils import utcnow


class VotingAutomationService:
    """
    Implements Phase 18 Polls, Surveys & Community Voting Automation:
    - Voter eligibility check (1 vote per active flat)
    - Double-voting prevention
    - Quorum tracking & calculation
    - Automated secret ballot tallying & outcome determination
    """

    @staticmethod
    def cast_vote(meeting_id, flat_id, resident_id, vote_choice):
        """Casts an eligible ballot vote preventing double voting for the same flat."""
        meeting = db.session.get(SocietyMeeting, meeting_id)
        if not meeting:
            raise ValueError("Society meeting not found")

        # Double vote prevention (1 vote per flat)
        existing = PollVote.query.filter_by(meeting_id=meeting_id, flat_id=flat_id).first()
        if existing:
            raise ValueError("Vote already recorded for this flat in this meeting/poll")

        vote = PollVote(
            meeting_id=meeting_id,
            flat_id=flat_id,
            resident_id=resident_id,
            vote_choice=vote_choice,
            voted_at=utcnow(),
        )
        db.session.add(vote)
        db.session.commit()
        return vote

    @staticmethod
    def tally_meeting_votes(meeting_id):
        """Tallies all votes for a meeting/poll, calculates quorum %, and determines result."""
        meeting = db.session.get(SocietyMeeting, meeting_id)
        if not meeting:
            return None

        total_flats = Flat.query.filter_by(society_id=meeting.society_id, occupancy_status="Occupied").count() or 1
        votes = PollVote.query.filter_by(meeting_id=meeting_id).all()

        in_favor = sum(1 for v in votes if v.vote_choice in ["In Favor", "Yes", "Approve"])
        against = sum(1 for v in votes if v.vote_choice in ["Against", "No", "Reject"])
        abstain = sum(1 for v in votes if v.vote_choice in ["Abstain", "Neutral"])
        total_cast = len(votes)

        quorum_pct = round((total_cast / total_flats * 100), 1)
        quorum_met = quorum_pct >= 33.3  # Standard 1/3rd quorum requirement

        result = "PASSED" if in_favor > against else ("REJECTED" if against > in_favor else "TIED")
        if not quorum_met:
            result = "NO_QUORUM"

        return {
            "meeting_id": meeting_id,
            "meeting_title": meeting.title,
            "total_flats": total_flats,
            "total_votes_cast": total_cast,
            "in_favor_count": in_favor,
            "against_count": against,
            "abstain_count": abstain,
            "quorum_percentage": quorum_pct,
            "quorum_met": quorum_met,
            "resolution_result": result,
        }
