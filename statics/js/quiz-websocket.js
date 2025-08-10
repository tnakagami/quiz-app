'use strict';

const QuizRoom = {};

(function () {
  // Create websocket based on scheme and url
  const createWebSocket = (location, url) => {
    const scheme = (location.protocol === 'https:' ? 'wss' : 'ws');
    const hostname = location.host;
    const socket = new WebSocket(`${scheme}://${hostname}/${url}`);

    return socket;
  };
  // Setup QuizRoom
  (() => {
    let room_socket;
    // Define sender
    const sender = (command, data = undefined) => {
      const message = {
        command: command,
        data: data,
      };
      room_socket.send(JSON.stringify(message));
    };
    /**
     * @brief Initialization of QuizRoom
     * @param[in] location:  window.location
     * @param[in] roomID:    roomID
     * @param[in] isOwner:   Describe whether user is owner or not (True: owner, False: not owner)
     * @param[in] callbacks: Instance of Callbacks class
    */
    QuizRoom.Init = (location, roomID, isOwner, callbacks) => {
      // Create WebSocket
      room_socket = createWebSocket(location, `ws/quizroom/${roomID}`);
      // Define processes when the client received message
      room_socket.onmessage = (event) => {
        const response = JSON.parse(event.data);
        const msgType = response.type;
        // Conduct process for each response from web-socket server
        switch (msgType) {
          case 'system':
            callbacks.chatLog(response.datetime, response.message);
            callbacks.updatePlayerStatuses(response.players);
            break;
          case 'sentNextQuiz':
            callbacks.setQuiz(response.data);
            callbacks.notifyReceivedQuiz(response.datetime, response.index, response.message);
            break;
          case 'startedAnswering':
            callbacks.start();
            break;
          case 'stoppedAnswering':
            callbacks.stop(response.datetime, response.message);
            break;
          case 'shareResult':
            callbacks.updateScoreTable(response.datetime, response.data);
            break;
          default:
            break;
        }
        //
        // Owner only
        //
        if (isOwner) {
          switch (msgType) {
            case 'resetCompleted':
              callbacks.resetQuiz(response.datetime, response.message);
              break;
            case 'sentAllQuizzes':
              callbacks.registeredQuizForAllMembers(response.datetime, response.message);
              break;
            case 'sentAnswers':
              callbacks.executeJudgement(response.datetime, response.message, response.data, response.correctAnswer);
              break;
            case 'shareResult':
              callbacks.endJudgement(response.datetime, response.message, response.isEnded);
              break;
            default:
              break;
          }
        }
        //
        // Player only
        //
        else {
          switch (msgType) {
            case 'resetCompleted':
              callbacks.resetPlayerScore();
              break;
            case 'sentAnswers':
              callbacks.registerExactAnswer(response.datetime, response.correctAnswer)
              break;
            default:
              break;
          }
        }
      };
    };
    //
    /**
     * @brief Reset quiz status
     */
    QuizRoom.ResetQuiz = () => {
      sender('resetQuiz');
    };
    /**
     * @brief Get next quiz
     */
    QuizRoom.GetNextQuiz = () => {
      sender('getNextQuiz');
    };
    /**
     * @brief Receive quiz
     */
    QuizRoom.ReceivedQuiz = () => {
      sender('receivedQuiz');
    };
    /**
     * @brief Start answer
     */
    QuizRoom.StartAnswer = () => {
      sender('startAnswer');
    };
    /**
     * @brief Answer quiz
     * @param[in] data Player's answer
     */
    QuizRoom.AnswerQuiz = (data) => {
      sender('answerQuiz', data);
    };
    /**
     * @brief Stop answer
     */
    QuizRoom.StopAnswer = () => {
      sender('stopAnswer');
    };
    /**
     * @brief Get answers
     */
    QuizRoom.GetAnswers = () => {
      sender('getAnswers');
    };
    /**
     * @brief Send result
     * @param[in] Judgement results for each player's answer
     */
    QuizRoom.SendResult = (data) => {
      sender('sendResult', data);
    };
  })();

  Object.freeze(QuizRoom);
})();