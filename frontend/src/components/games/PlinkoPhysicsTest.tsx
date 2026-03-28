import React from 'react';

// Physics constants
const GRAVITY = 0.3;
const BALL_RADIUS = 8;
const PEG_RADIUS = 4;
const BOUNCE_DAMPING = 0.7;
const FRICTION = 0.99;
const MIN_VELOCITY = 0.1;
const MAX_BOUNCE_ANGLE = Math.PI / 3;

interface BallPosition {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

interface PegPosition {
  x: number;
  y: number;
}

export const PlinkoPhysicsTest: React.FC = () => {
  const testCollisionDetection = () => {
    // Test 1: No collision
    const ball1: BallPosition = { x: 100, y: 100, vx: 0, vy: 0 };
    const peg1: PegPosition = { x: 200, y: 200 };
    
    const checkPegCollision = (ballPos: BallPosition, peg: PegPosition): boolean => {
      const dx = ballPos.x - peg.x;
      const dy = ballPos.y - peg.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      return distance < (BALL_RADIUS + PEG_RADIUS);
    };
    
    const result1 = checkPegCollision(ball1, peg1);
    console.log('Test 1 - No collision:', result1 === false ? 'PASS' : 'FAIL');
    
    // Test 2: Collision
    const ball2: BallPosition = { x: 100, y: 100, vx: 0, vy: 0 };
    const peg2: PegPosition = { x: 105, y: 105 };
    
    const result2 = checkPegCollision(ball2, peg2);
    console.log('Test 2 - Collision:', result2 === true ? 'PASS' : 'FAIL');
  };
  
  const testBouncePhysics = () => {
    const handlePegBounce = (ballPos: BallPosition, peg: PegPosition): BallPosition => {
      // Calculate collision normal
      const dx = ballPos.x - peg.x;
      const dy = ballPos.y - peg.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      
      // Normalize collision vector
      const nx = dx / distance;
      const ny = dy / distance;
      
      // Calculate relative velocity along collision normal
      const relativeVelocity = ballPos.vx * nx + ballPos.vy * ny;
      
      // Don't bounce if velocities are separating
      if (relativeVelocity > 0) {
        return ballPos;
      }
      
      // Calculate new velocity with bounce damping
      const bounceFactor = -BOUNCE_DAMPING;
      const newVx = ballPos.vx + bounceFactor * relativeVelocity * nx;
      const newVy = ballPos.vy + bounceFactor * relativeVelocity * ny;
      
      // Limit bounce angle to prevent unrealistic bouncing
      const velocity = Math.sqrt(newVx * newVx + newVy * newVy);
      let angle = Math.atan2(newVy, newVx);
      
      // Constrain angle to reasonable range
      if (Math.abs(angle) > MAX_BOUNCE_ANGLE) {
        angle = Math.sign(angle) * MAX_BOUNCE_ANGLE;
      }
      
      // Apply angle constraint
      const constrainedVx = velocity * Math.cos(angle);
      const constrainedVy = velocity * Math.sin(angle);
      
      // Move ball outside of peg to prevent sticking
      const overlap = (BALL_RADIUS + PEG_RADIUS) - distance;
      const separateX = nx * overlap * 1.1;
      const separateY = ny * overlap * 1.1;
      
      return {
        x: ballPos.x + separateX,
        y: ballPos.y + separateY,
        vx: constrainedVx,
        vy: constrainedVy
      };
    };
    
    // Test bounce with ball moving directly toward peg
    const ball: BallPosition = { x: 100, y: 50, vx: 0, vy: 2 };
    const peg: PegPosition = { x: 100, y: 100 };
    
    const result = handlePegBounce(ball, peg);
    console.log('Bounce test - Velocity reversal:', result.vy < 0 ? 'PASS' : 'FAIL');
    console.log('Bounce test - Position separation:', Math.abs(result.y - peg.y) > (BALL_RADIUS + PEG_RADIUS) ? 'PASS' : 'FAIL');
  };
  
  return (
    <div>
      <h2>Plinko Physics Test</h2>
      <button onClick={testCollisionDetection}>Test Collision Detection</button>
      <button onClick={testBouncePhysics}>Test Bounce Physics</button>
      <p>Open browser console to see test results</p>
    </div>
  );
};

export default PlinkoPhysicsTest;