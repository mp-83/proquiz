from datetime import datetime, timedelta

import pytest

from app.domain_entities import User
from app.domain_entities.user import UserFactory, WordDigest
from app.domain_service.data_transfer.answer import AnswerDTO
from app.domain_service.data_transfer.game import GameDTO
from app.domain_service.data_transfer.match import MatchDTO
from app.domain_service.data_transfer.question import QuestionDTO
from app.domain_service.data_transfer.reaction import ReactionDTO
from app.domain_service.validation.logical import (
    RetrieveObject,
    ValidateMatchImport,
    ValidateNewCodeMatch,
    ValidatePlayCode,
    ValidatePlayLand,
    ValidatePlayNext,
    ValidatePlaySign,
    ValidatePlayStart,
)
from app.exceptions import NotFoundObjectError, ValidateError


class TestCaseBase:
    @pytest.fixture(autouse=True)
    def setUp(self, dbsession):
        self.question_dto = QuestionDTO(session=dbsession)
        self.answer_dto = AnswerDTO(session=dbsession)
        self.reaction_dto = ReactionDTO(session=dbsession)
        self.match_dto = MatchDTO(session=dbsession)
        self.game_dto = GameDTO(session=dbsession)


class TestCaseRetrieveObject:
    def t_objectNotFound(self, dbsession):
        with pytest.raises(NotFoundObjectError):
            RetrieveObject(uid=1, otype="match", db_session=dbsession).get()

    def t_objectIsOfCorrectType(self, dbsession):
        user = UserFactory(db_session=dbsession).fetch()
        obj = RetrieveObject(uid=user.uid, otype="user", db_session=dbsession).get()
        assert obj == user


class TestCaseLandEndPoint:
    def t_matchDoesNotExists(self, dbsession):
        with pytest.raises(NotFoundObjectError):
            ValidatePlayLand(
                match_uhash="wrong-hash", db_session=dbsession
            ).valid_match()


class TestCaseCodeEndPoint(TestCaseBase):
    def t_wrongCode(self, dbsession):
        with pytest.raises(NotFoundObjectError):
            ValidatePlayCode(match_code="2222", db_session=dbsession).valid_match()

    def t_matchActiveness(self, dbsession):
        ten_hours_ago = datetime.now() - timedelta(hours=40)
        two_hours_ago = datetime.now() - timedelta(hours=3600)
        match = self.match_dto.save(
            self.match_dto.new(
                with_code=True,
                from_time=ten_hours_ago,
                to_time=two_hours_ago,
            )
        )
        with pytest.raises(ValidateError) as err:
            ValidatePlayCode(match_code=match.code, db_session=dbsession).valid_match()

        assert err.value.message == "Expired match"


class TestCaseSignEndPoint:
    def t_wrongToken(self, dbsession):
        original_email = "user@test.io"

        email_digest = WordDigest(original_email).value()
        token_digest = WordDigest("01112021").value()
        email = f"{email_digest}@progame.io"
        User(
            email=email,
            email_digest=email_digest,
            token_digest=token_digest,
            db_session=dbsession,
        ).save()
        with pytest.raises(NotFoundObjectError):
            ValidatePlaySign(
                original_email, "25121980", db_session=dbsession
            ).is_valid()


class TestCaseStartEndPoint(TestCaseBase):
    def t_publicUserRestrictedMatch(self, dbsession):
        match = self.match_dto.new(is_restricted=True)
        self.match_dto.save(match)
        user = User(email="user@test.project", db_session=dbsession).save()
        with pytest.raises(ValidateError) as err:
            ValidatePlayStart(
                match_uid=match.uid,
                user_uid=user.uid,
                password=match.password,
                db_session=dbsession,
            ).is_valid()

        assert err.value.message == "User cannot access this match"

    def t_privateMatchRequiresPassword(self, dbsession):
        match = self.match_dto.new(is_restricted=True)
        self.match_dto.save(match)
        user = UserFactory(signed=True, db_session=dbsession).fetch()
        with pytest.raises(ValidateError) as err:
            ValidatePlayStart(
                match_uid=match.uid,
                user_uid=user.uid,
                password="",
                db_session=dbsession,
            ).is_valid()

        assert err.value.message == "Password is required for private matches"

    def t_userDoesNotExists(self, dbsession):
        with pytest.raises(NotFoundObjectError):
            ValidatePlayStart(user_uid=1, db_session=dbsession).valid_user()

    def t_invalidPassword(self, dbsession):
        match = self.match_dto.new(is_restricted=True)
        self.match_dto.save(match)
        UserFactory(signed=True, db_session=dbsession).fetch()
        with pytest.raises(ValidateError) as err:
            ValidatePlayStart(
                match_uid=match.uid, password="Invalid", db_session=dbsession
            ).is_valid()

        assert err.value.message == "Password mismatch"


class TestCaseNextEndPoint(TestCaseBase):
    def t_cannotAcceptSameReactionAgain(self, dbsession):
        # despite the delay between the two (which respects the DB constraint)
        match = self.match_dto.save(self.match_dto.new())
        game = self.game_dto.new(match_uid=match.uid, index=0)
        self.game_dto.save(game)
        question = self.question_dto.new(
            text="Where is London?", game_uid=game.uid, position=0, db_session=dbsession
        )
        self.question_dto.save(question)
        answer = self.answer_dto.new(
            question=question, text="UK", position=1, db_session=dbsession
        )
        self.answer_dto.save(answer)
        user = UserFactory(email="user@test.project", db_session=dbsession).fetch()

        reaction = self.reaction_dto.new(
            match=match,
            question=question,
            user=user,
            game_uid=game.uid,
            answer_uid=answer.uid,
            db_session=dbsession,
        )
        self.reaction_dto.save(reaction)

        with pytest.raises(ValidateError):
            ValidatePlayNext(
                user_uid=user.uid, question_uid=question.uid, db_session=dbsession
            ).valid_reaction()

    def t_answerDoesNotBelongToQuestion(self, dbsession):
        # simulate a more realistic case
        match = self.match_dto.save(self.match_dto.new())
        game = self.game_dto.new(match_uid=match.uid, index=0)
        self.game_dto.save(game)
        question = self.question_dto.new(
            text="Where is London?", game_uid=game.uid, position=0, db_session=dbsession
        )
        self.question_dto.save(question)
        answer = self.answer_dto.new(
            question_uid=question.uid, text="UK", position=1, db_session=dbsession
        )
        self.answer_dto.save(answer)
        with pytest.raises(ValidateError):
            ValidatePlayNext(
                answer_uid=answer.uid, question_uid=10, db_session=dbsession
            ).valid_answer()

    def t_answerDoesNotExists(self, dbsession):
        with pytest.raises(NotFoundObjectError):
            ValidatePlayNext(answer_uid=10000, db_session=dbsession).valid_answer()

    def t_userDoesNotExists(self, dbsession):
        with pytest.raises(NotFoundObjectError):
            ValidatePlayNext(user_uid=1, db_session=dbsession).valid_user()

    def t_matchDoesNotExists(self, dbsession):
        with pytest.raises(NotFoundObjectError):
            ValidatePlayNext(match_uid=1, db_session=dbsession).valid_match()


class TestCaseCreateMatch:
    def t_fromTimeGreaterThanToTime(self):
        # to avoid from_time to be < datetime.now() when
        # the check is performed, the value is increased
        # by two seconds (or we mock datetime.now)
        with pytest.raises(ValidateError) as e:
            ValidateNewCodeMatch(
                from_time=(datetime.now() + timedelta(seconds=2)),
                to_time=(datetime.now() - timedelta(seconds=10)),
            ).is_valid()

        assert e.value.message == "to-time must be greater than from-time"

    def t_fromTimeIsExpired(self):
        with pytest.raises(ValidateError) as e:
            ValidateNewCodeMatch(
                from_time=(datetime.now() - timedelta(seconds=1)),
                to_time=(datetime.now() + timedelta(days=1)),
            ).is_valid()

        assert e.value.message == "from-time must be greater than now"


class TestCaseImportFromYaml:
    def t_matchDoesNotExists(self, dbsession):
        with pytest.raises(NotFoundObjectError):
            ValidateMatchImport(match_uid=1, db_session=dbsession).valid_match()
