import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.domain_entities import Game, Match, Reaction
from app.domain_entities.user import UserFactory
from app.domain_service.data_transfer.question import QuestionDTO


class TestCaseUser:
    @pytest.fixture(autouse=True)
    def setUp(self, dbsession):
        self.question_dto = QuestionDTO(session=dbsession)

    def t_list_all_players(self, client: TestClient, dbsession):
        first_match = Match(db_session=dbsession).save()
        first_game = Game(
            match_uid=first_match.uid, index=0, db_session=dbsession
        ).save()
        second_match = Match(db_session=dbsession).save()
        second_game = Game(
            match_uid=second_match.uid, index=0, db_session=dbsession
        ).save()
        question_1 = self.question_dto.new(
            text="3*3 = ", time=0, position=0, db_session=dbsession
        )
        self.question_dto.save(question_1)

        question_2 = self.question_dto.new(
            text="1+1 = ", time=1, position=1, db_session=dbsession
        )
        self.question_dto.save(question_2)

        user_1 = UserFactory(db_session=dbsession).fetch()
        user_2 = UserFactory(db_session=dbsession).fetch()
        user_3 = UserFactory(db_session=dbsession).fetch()
        Reaction(
            match=first_match,
            question=question_1,
            user=user_1,
            game_uid=first_game.uid,
            db_session=dbsession,
        ).save()
        Reaction(
            match=first_match,
            question=question_2,
            user=user_1,
            game_uid=first_game.uid,
            db_session=dbsession,
        ).save()
        Reaction(
            match=first_match,
            question=question_1,
            user=user_2,
            game_uid=first_game.uid,
            db_session=dbsession,
        ).save()
        Reaction(
            match=first_match,
            question=question_1,
            user=user_3,
            game_uid=first_game.uid,
            db_session=dbsession,
        ).save()

        Reaction(
            match=second_match,
            question=question_1,
            user=user_2,
            game_uid=second_game.uid,
            db_session=dbsession,
        ).save()
        Reaction(
            match=second_match,
            question=question_1,
            user=user_1,
            game_uid=second_game.uid,
            db_session=dbsession,
        ).save()

        response = client.get(f"{settings.API_V1_STR}/players/{first_match.uid}")
        assert response.ok
        assert response.json()["players"] == [
            {"full_name": None, "is_active": True},
            {"full_name": None, "is_active": True},
            {"full_name": None, "is_active": True},
        ]
