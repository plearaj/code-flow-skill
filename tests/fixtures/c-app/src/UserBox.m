#import "UserBox.h"

@implementation UserBox

- (NSString *)recordForUser:(NSString *)userId {
    return [self normalize:userId];
}

/** Lower-cases a value. Not declared in the interface, so it is private. */
- (NSString *)normalize:(NSString *)value {
    return [value lowercaseString];
}

@end
