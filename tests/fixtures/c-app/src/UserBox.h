#import <Foundation/Foundation.h>

/** Holds one user record and hands it back normalized. */
@interface UserBox : NSObject

/** Returns the record for a user id. */
- (NSString *)recordForUser:(NSString *)userId;

@end
