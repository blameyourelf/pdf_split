const { Model } = require('objection');

class UserPreference extends Model {
  static get tableName() {
    return 'user_preferences';
  }

  static get relationMappings() {
    const User = require('./User');
    const Ward = require('./Ward');

    return {
      user: {
        relation: Model.BelongsToOneRelation,
        modelClass: User,
        join: {
          from: 'user_preferences.user_id',
          to: 'users.id'
        }
      },
      defaultWard: {
        relation: Model.BelongsToOneRelation,
        modelClass: Ward,
        join: {
          from: 'user_preferences.default_ward_id',
          to: 'wards.id'
        }
      }
    };
  }
}

module.exports = UserPreference;
