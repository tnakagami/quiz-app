'use strict';

const QuizRoom = {};

(function () {
  // Create websocket based on scheme and url
  const createWebSocket = (location, url) => {
    const scheme = (location === 'https:' ? 'wss' : 'ws');
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
        // Codunct process for each response from web-socket server
        switch (msgType) {
          case 'system':
            callbacks.chatLog(response.datetime, response.message);
            break;
          case 'sentNextQuiz':
            callbacks.setQuiz(response.data);
            callbacks.notifyReceivedQuiz(response.index);
            break;
          case 'startAnswer':
            callbacks.start();
            break;
          case 'stopAnswer':
            callbacks.stop();
            break;
          case 'shareResult':
            callbacks.updateScoreTable(response.data);
            break;
          default:
            break;
        }
        // Only owner
        if (isOwner) {
          switch (msgType) {
            case 'resetQuiz':
              callbacks.resetQuiz(response.data);
              break;
            case 'sentAllQuizzes':
              callbacks.registeredQuizForAllMembers();
              break;
            case 'sentAnswers':
              callbacks.executeJudgement(response.data, response.correctAnswer);
              break;
            case 'shareResult':
              callbacks.endJudgement(response.isEnded);
              break;
            default:
              break;
          }
        }
        // Only player
        else {
          switch (msgType) {
            case 'sentAnswers':
              callbacks.registerExactAnswer(response.correctAnswer)
              break;
            default:
              break;
          }
        }
      };
    };
    // Register commands
    QuizRoom.ResetQuiz = () => {
      /**
       * @brief Reset quiz status
       */
      sender('resetQuiz');
    };
    QuizRoom.GetNextQuiz = () => {
      /**
       * @brief Get next quiz
       */
      sender('getNextQuiz');
    };
    QuizRoom.ReceivedQuiz = () => {
      /**
       * @brief Receive quiz
       */
      sender('receivedQuiz');
    };
    QuizRoom.StartAnswer = () => {
      /**
       * @brief Start answer
       */
      sender('startAnswer');
    };
    QuizRoom.AnswerQuiz = (data) => {
      /**
       * @brief Answer quiz
       */
      sender('answerQuiz', data);
    };
    QuizRoom.StopAnswer = () => {
      /**
       * @brief Stop answer
       */
      sender('stopAnswer');
    };
    QuizRoom.GetAnswers = () => {
      /**
       * @brief Get answers
       */
      sender('getAnswers');
    };
    QuizRoom.SendResult = (data) => {
      /**
       * @brief Send result
       */
      sender('sendResult', data);
    };
  })();

  Object.freeze(QuizRoom);
})();