from datetime import datetime, timedelta

import pytest

from app.constants import MATCH_HASH_LEN, MATCH_PASSWORD_LEN
from app.domain_service.data_transfer.answer import AnswerDTO
from app.domain_service.data_transfer.game import GameDTO
from app.domain_service.data_transfer.match import (
    MatchCode,
    MatchDTO,
    MatchHash,
    MatchPassword,
)
from app.domain_service.data_transfer.question import QuestionDTO
from app.domain_service.data_transfer.reaction import ReactionDTO
from app.domain_service.data_transfer.user import UserDTO
from app.exceptions import NotUsableQuestionError


class TestCaseMatchModel:
    @pytest.fixture(autouse=True)
    def setUp(self, db_session):
        self.question_dto = QuestionDTO(session=db_session)
        self.answer_dto = AnswerDTO(session=db_session)
        self.match_dto = MatchDTO(session=db_session)
        self.game_dto = GameDTO(session=db_session)
        self.user_dto = UserDTO(session=db_session)

    def test_questionsPropertyReturnsTheExpectedResults(self):
        match = self.match_dto.save(self.match_dto.new())
        first_game = self.game_dto.new(match_uid=match.uid, index=0)
        self.game_dto.save(first_game)
        question = self.question_dto.new(
            text="Where is London?",
            game_uid=first_game.uid,
            position=0,
        )
        self.question_dto.save(question)
        second_game = self.game_dto.new(match_uid=match.uid, index=1)
        self.game_dto.save(second_game)

        question = self.question_dto.new(
            text="Where is Vienna?",
            game_uid=second_game.uid,
            position=0,
        )
        self.question_dto.save(question)
        assert match.questions[0][0].text == "Where is London?"
        assert match.questions[0][0].game == first_game
        assert match.questions[1][0].text == "Where is Vienna?"
        assert match.questions[1][0].game == second_game

    def test_createMatchWithHash(self):
        match = self.match_dto.save(self.match_dto.new(with_code=False))
        assert match.uhash is not None
        assert len(match.uhash) == MATCH_HASH_LEN

    def test_createRestrictedMatch(self):
        match = self.match_dto.save(self.match_dto.new(is_restricted=True))
        assert match.uhash
        assert len(match.password) == MATCH_PASSWORD_LEN

    def test_updateTextExistingQuestion(self):
        match = self.match_dto.save(self.match_dto.new())
        game = self.game_dto.new(match_uid=match.uid)
        self.game_dto.save(game)
        question = self.question_dto.new(
            text="Where is London?",
            game_uid=game.uid,
            position=0,
        )
        self.question_dto.save(question)

        n = self.question_dto.count()
        self.match_dto.update_questions(
            match,
            [
                {
                    "uid": question.uid,
                    "text": "What is the capital of Norway?",
                }
            ],
        )
        no_new_questions = n == self.question_dto.count()
        assert no_new_questions
        assert question.text == "What is the capital of Norway?"

    def test_createMatchUsingTemplateQuestions(self):
        question_1 = self.question_dto.new(text="Where is London?", position=0)
        question_2 = self.question_dto.new(text="Where is Vienna?", position=1)
        self.question_dto.add_many([question_1, question_2])

        answer = self.answer_dto.new(
            question_uid=question_1.uid,
            text="question2.answer1",
            position=1,
        )
        self.answer_dto.save(answer)

        new_match = self.match_dto.save(self.match_dto.new(with_code=False))
        questions_cnt = self.question_dto.count()
        answers_cnt = self.answer_dto.count()
        self.match_dto.import_template_questions(
            new_match, [question_1.uid, question_2.uid]
        )
        assert self.question_dto.count() == questions_cnt + 2
        assert self.answer_dto.count() == answers_cnt + 0

    def test_cannotUseIdsOfQuestionAlreadyAssociateToAGame(self):
        match = self.match_dto.save(self.match_dto.new())
        game = self.game_dto.new(match_uid=match.uid)
        self.game_dto.save(game)
        question = self.question_dto.new(
            text="Where is London?",
            game_uid=game.uid,
            position=3,
        )
        self.question_dto.save(question)
        with pytest.raises(NotUsableQuestionError):
            self.match_dto.import_template_questions(match, [question.uid])

    def test_moveFirstQuestionToSecondGame(self):
        match = self.match_dto.save(self.match_dto.new())
        first_game = self.game_dto.new(match_uid=match.uid, index=0)
        self.game_dto.save(first_game)
        second_game = self.game_dto.new(match_uid=match.uid, index=1)
        self.game_dto.save(second_game)
        question_1 = self.question_dto.new(
            text="Where is London?",
            game_uid=first_game.uid,
            position=0,
        )
        self.question_dto.save(question_1)
        question_2 = self.question_dto.new(
            text="Where is New York?",
            game_uid=first_game.uid,
            position=1,
        )
        self.question_dto.save(question_2)
        question_3 = self.question_dto.new(
            text="Where is Tokyo?",
            game_uid=second_game.uid,
            position=1,
        )
        self.question_dto.save(question_3)
        data = {"questions": [{"uid": question_1.uid, "game_uid": second_game.uid}]}
        self.match_dto.update(match, **data)
        assert question_1.game == second_game

    def test_updateGameProperty(self):
        match = self.match_dto.save(self.match_dto.new())
        game = self.game_dto.new(match_uid=match.uid)
        data = {"games": [{"uid": game.uid, "order": False}]}
        self.match_dto.update(match, **data)
        assert not game.order

    def test_matchCannotBePlayedIfAreNoLeftAttempts(self, db_session):
        match = self.match_dto.save(self.match_dto.new())
        game = self.game_dto.new(match_uid=match.uid)
        self.game_dto.save(game)
        user = self.user_dto.new(email="user@test.project")
        self.user_dto.save(user)
        question = self.question_dto.new(
            text="1+1 is = to", position=0, game_uid=game.uid
        )
        self.question_dto.save(question)
        reaction_dto = ReactionDTO(session=db_session)
        reaction_dto.save(
            reaction_dto.new(
                question=question,
                user=user,
                match=match,
                game_uid=game.uid,
            )
        )

        assert match.reactions[0].user == user
        assert match.left_attempts(user) == 0

    def test_10(self, db_session):
        """
        GIVEN: a match already started once
        WHEN: the user wants to start
        THEN: the user should be able to do it indefinitely because
                because the times parameter of the match is 0
        """
        match = self.match_dto.new(times=0)
        self.match_dto.save(match)
        game = self.game_dto.new(match_uid=match.uid)
        self.game_dto.save(game)
        user = self.user_dto.new(email="user@test.project")
        self.user_dto.save(user)
        question = self.question_dto.new(
            text="1+1 is = to", position=0, game_uid=game.uid
        )
        self.question_dto.save(question)
        reaction_dto = ReactionDTO(session=db_session)
        reaction_dto.save(
            reaction_dto.new(
                question=question,
                user=user,
                match=match,
                game_uid=game.uid,
            )
        )

        assert match.reactions[0].user == user
        assert match.left_attempts(user) == 1

    def test_insertBooleanQuestionsIntoTwoDifferentGames(self):
        questions = [
            {
                "answers": [{"text": True}, {"text": False}],
                "text": "There is no cream in the traditional Carbonara?",
            },
        ]
        match = self.match_dto.save(self.match_dto.new())
        first_game = self.game_dto.save(self.game_dto.new(match_uid=match.uid, index=0))
        self.match_dto.insert_questions(match, questions, game_uid=first_game.uid)

        assert match.questions[0][0].boolean
        assert match.questions[0][0].game_uid == first_game.uid

        assert match.questions[0][0].answers_list[0]["boolean"]
        assert match.questions[0][0].answers_list[0]["text"] == "True"
        assert match.questions[0][0].answers_list[0]["is_correct"]
        assert not match.questions[0][0].answers_list[1]["is_correct"]

        second_game = self.game_dto.save(
            self.game_dto.new(match_uid=match.uid, index=1)
        )
        questions = [
            {
                "answers": [{"text": False}, {"text": True}],
                "text": "Biscuits are the same in the US and in the UK?",
            },
        ]
        self.match_dto.insert_questions(match, questions, game_uid=second_game.uid)

        assert match.questions[1][0].game_uid == second_game.uid
        assert match.questions[1][0].answers_list[1]["boolean"]
        assert match.questions[1][0].answers_list[0]["text"] == "False"
        assert match.questions[1][0].answers_list[0]["is_correct"]

    def test_secondGameIsTheSameOfPreviousQuestionsUnlessSpecified(self):
        match = self.match_dto.save(self.match_dto.new())
        first_game = self.game_dto.save(self.game_dto.new(match_uid=match.uid, index=0))
        questions = [
            {
                "answers": [{"text": False}, {"text": True}],
                "text": "Question.1",
            },
        ]
        self.match_dto.insert_questions(match, questions, game_uid=first_game.uid)
        assert match.questions[0][0].game_uid == first_game.uid

        questions = [
            {
                "answers": [{"text": False}, {"text": True}],
                "text": "Question.2",
            },
        ]
        self.match_dto.insert_questions(match, questions)
        assert match.questions[0][1].game_uid == first_game.uid


class TestCaseMatchHash:
    def test_hashMustBeUniqueForEachMatch(self, db_session, mocker, match_dto):
        # the first call return a value already used
        random_method = mocker.patch(
            "app.domain_service.data_transfer.match.choices",
            side_effect=["LINK-HASH1", "LINK-HASH2"],
        )
        match_dto.save(match_dto.new(uhash="LINK-HASH1"))

        MatchHash(db_session=db_session).get_hash()
        assert random_method.call_count == 2


class TestCaseMatchPassword:
    def test_passwordUniqueForEachMatch(self, db_session, mocker, match_dto):
        # the first call return a value already used
        random_method = mocker.patch(
            "app.domain_service.data_transfer.match.choices",
            side_effect=["00321", "34550"],
        )
        match_dto.save(match_dto.new(uhash="AEDRF", password="00321"))

        MatchPassword(uhash="AEDRF", db_session=db_session).get_value()
        assert random_method.call_count == 2


class TestCaseMatchCode:
    def test_codeUniqueForEachMatchAtThatTime(self, db_session, mocker, match_dto):
        tomorrow = datetime.now() + timedelta(days=1)
        random_method = mocker.patch(
            "app.domain_service.data_transfer.match.choices",
            side_effect=["8363", "7775"],
        )
        match_dto.save(match_dto.new(code=8363, expires=tomorrow))

        MatchCode(db_session=db_session).get_code()
        assert random_method.call_count == 2
