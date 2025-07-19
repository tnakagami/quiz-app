from django import template

register = template.Library()

##
# @brief Check whether request user is room owner or not
# @param room Instance of QuizRoom
# @param user Request user
# @return bool Judgement result
# @retval True  The request user is room owner
# @retval False The request user is not room owner
@register.filter
def is_owner(room, user):
  return room.is_owner(user)

##
# @brief Get user's score
# @param score Instance of Score
# @param user Request user
# @param The value of score
@register.filter
def get_user_score(score, pk):
  return score.detail[str(pk)]